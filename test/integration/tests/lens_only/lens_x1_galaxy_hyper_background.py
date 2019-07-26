import os

import autofit as af
from autolens.model.galaxy import galaxy as g
from autolens.model.galaxy import galaxy_model as gm
from autolens.pipeline.phase import phase_imaging
from autolens.pipeline import pipeline as pl
from autolens.model.profiles import light_profiles as lp
from test.integration import integration_util
from test.simulation import simulation_util

test_type = "lens_only"
test_name = "lens_x1_galaxy_hyper_background"

test_path = "{}/../../".format(os.path.dirname(os.path.realpath(__file__)))
output_path = test_path + "output/"
config_path = test_path + "config"
af.conf.instance = af.conf.Config(config_path=config_path, output_path=output_path)


def pipeline():

    integration_util.reset_paths(test_name=test_name, output_path=output_path)
    ccd_data = simulation_util.load_test_ccd_data(
        data_type="lens_only_bulge_and_disk", data_resolution="LSST"
    )
    pipeline = make_pipeline(test_name=test_name)
    pipeline.run(data=ccd_data)


def make_pipeline(test_name):

    phase1 = phase_imaging.PhaseImaging(
        phase_name="phase_1",
        phase_folders=[test_type, test_name],
        galaxies=dict(lens=gm.GalaxyModel(redshift=0.5, light=lp.EllipticalSersic)),
        optimizer_class=af.MultiNest,
    )

    phase1.optimizer.const_efficiency_mode = True
    phase1.optimizer.n_live_points = 40
    phase1.optimizer.sampling_efficiency = 0.8

    phase1 = phase1.extend_with_multiple_hyper_phases(
        hyper_galaxy=True, include_background_sky=True, include_background_noise=True
    )

    class HyperLensPlanePhase(phase_imaging.PhaseImaging):
        def pass_priors(self, results):

            self.galaxies = results.from_phase("phase_1").variable.galaxies

            self.galaxies.lens.hyper_galaxy = (
                results.last.hyper_combined.constant.galaxies.lens.hyper_galaxy
            )

            # self.hyper_image_sky = (
            #     results.last.hyper_combined.constant.hyper_image_sky
            # )

            self.hyper_noise_background = (
                results.last.hyper_combined.constant.hyper_noise_background
            )

    phase2 = HyperLensPlanePhase(
        phase_name="phase_2",
        phase_folders=[test_type, test_name],
        galaxies=dict(
            lens=gm.GalaxyModel(
                redshift=0.5, light=lp.EllipticalSersic, hyper_galaxy=g.HyperGalaxy
            )
        ),
        optimizer_class=af.MultiNest,
    )

    phase2.optimizer.const_efficiency_mode = True
    phase2.optimizer.n_live_points = 40
    phase2.optimizer.sampling_efficiency = 0.8

    return pl.PipelineImaging(test_name, phase1, phase2)


if __name__ == "__main__":
    pipeline()
