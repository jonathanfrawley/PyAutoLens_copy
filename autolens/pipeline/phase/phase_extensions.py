import copy

import numpy as np
from typing import cast

import autofit as af
from autolens import exc
from autolens.lens import lens_data as ld, lens_fit
from autolens.model.galaxy import galaxy as g
from autolens.model.hyper import hyper_data as hd
from autolens.model.inversion import pixelizations as px
from autolens.model.inversion import regularization as rg
from autolens.pipeline.phase import phase as ph
from autolens.pipeline.phase import phase_imaging
from autolens.pipeline.phase.phase import setup_phase_mask
from autolens.pipeline.plotters import hyper_plotters


class HyperPhase(object):
    def __init__(
            self,
            phase: ph.Phase,
            hyper_name: str
    ):
        """
        Abstract HyperPhase. Wraps a regular phase, performing that phase before performing the action
        specified by the run_hyper.

        Parameters
        ----------
        phase
            A regular phase
        """
        self.phase = phase
        self.hyper_name = hyper_name

    def run_hyper(self, *args, **kwargs) -> af.Result:
        """
        Run the hyper phase.

        Parameters
        ----------
        args
        kwargs

        Returns
        -------
        result
            The result of the hyper phase.
        """
        raise NotImplementedError()

    def make_hyper_phase(self) -> ph.Phase:
        """
        Returns
        -------
        hyper_phase
            A copy of the original phase with a modified name and path
        """

        phase = copy.deepcopy(self.phase)

        phase_folders = phase.phase_folders
        phase_folders.append(phase.phase_name)

        phase.optimizer = phase.optimizer.copy_with_name_extension(
            self.hyper_name
        )

        return phase

    def run(self, data, results: af.ResultsCollection = None, **kwargs) -> af.Result:
        """
        Run the normal phase and then the hyper phase.

        Parameters
        ----------
        data
            Data
        results
            Results from previous phases.
        kwargs

        Returns
        -------
        result
            The result of the phase, with a hyper result attached as an attribute with the hyper_name of this
            phase.
        """
        results = copy.deepcopy(results) if results is not None else af.ResultsCollection()
        result = self.phase.run(data, results=results, **kwargs)
        results.add(self.phase.phase_name, result)
        hyper_result = self.run_hyper(
            data=data,
            results=results,
            **kwargs
        )
        setattr(result, self.hyper_name, hyper_result)
        return result

    def __getattr__(self, item):
        return getattr(self.phase, item)


# noinspection PyAbstractClass
class VariableFixingHyperPhase(HyperPhase):

    def __init__(
            self,
            phase: ph.Phase,
            hyper_name: str,
            variable_classes=tuple(),
            default_classes=None
    ):
        super().__init__(
            phase=phase,
            hyper_name=hyper_name
        )
        self.default_classes = default_classes or dict()
        self.variable_classes = variable_classes

    def make_hyper_phase(self):
        phase = super().make_hyper_phase()

        phase.const_efficiency_mode = af.conf.instance.non_linear.get(
            'MultiNest',
            'extension_inversion_const_efficiency_mode',
            bool
        )
        phase.optimizer.sampling_efficiency = af.conf.instance.non_linear.get(
            'MultiNest',
            'extension_inversion_sampling_efficiency',
            float
        )
        phase.optimizer.n_live_points = af.conf.instance.non_linear.get(
            'MultiNest',
            'extension_inversion_n_live_points',
            int
        )

        return phase

    def run_hyper(self, data, results=None, **kwargs):
        """
        Run the phase, overriding the optimizer's variable instance with one created to
        only fit pixelization hyperparameters.
        """

        variable = copy.deepcopy(results.last.variable)
        self.transfer_classes(results.last.constant, variable)
        self.add_defaults(variable)

        phase = self.make_hyper_phase()
        phase.optimizer.variable = variable

        return phase.run(data, results=results, **kwargs)

    def add_defaults(self, variable: af.ModelMapper):
        """
        Add default prior models for each of the items in the defaults dictionary.

        Provides a way of specifying new prior models to be included at the top level
        in this phase.

        Parameters
        ----------
        variable
            The variable object to be used in this phase to which default prior
            models are attached.
        """
        for key, value in self.default_classes.items():
            if not hasattr(variable, key):
                setattr(variable, key, value)

    def transfer_classes(self, instance, mapper):
        """
        Recursively overwrite priors in the mapper with constant values from the
        instance except where the containing class is the descendant of a listed class.

        Parameters
        ----------
        instance
            The best fit from the previous phase
        mapper
            The prior variable from the previous phase
        """
        for key, instance_value in instance.__dict__.items():
            try:
                mapper_value = getattr(mapper, key)
                if isinstance(mapper_value, af.Prior):
                    setattr(mapper, key, instance_value)
                if not any(
                        isinstance(
                            instance_value,
                            cls
                        )
                        for cls in self.variable_classes
                ):
                    try:
                        self.transfer_classes(
                            instance_value,
                            mapper_value)
                    except AttributeError:
                        setattr(mapper, key, instance_value)
            except AttributeError:
                pass


class InversionPhase(VariableFixingHyperPhase):
    """
    Phase that makes everything in the variable from the previous phase equal to the
    corresponding value from the best fit except for variables associated with
    pixelization
    """

    def __init__(
            self,
            phase: ph.Phase,
            variable_classes=(
                    px.Pixelization,
                    rg.Regularization
            ),
            default_classes=None
    ):
        super().__init__(
            phase=phase,
            variable_classes=variable_classes,
            hyper_name="inversion",
            default_classes=default_classes
        )

    @property
    def uses_inversion(self):
        return True

    @property
    def uses_hyper_images(self):
        return True


class InversionBackgroundSkyPhase(InversionPhase):
    """
    Phase that makes everything in the variable from the previous phase equal to the
    corresponding value from the best fit except for variables associated with
    pixelization
    """

    def __init__(self, phase: ph.Phase):
        super().__init__(
            phase=phase,
            variable_classes=(
                px.Pixelization,
                rg.Regularization,
                hd.HyperImageSky
            ),
            default_classes={
                "hyper_image_sky": hd.HyperImageSky
            }
        )


class InversionBackgroundNoisePhase(InversionPhase):
    """
    Phase that makes everything in the variable from the previous phase equal to the
    corresponding value from the best fit except for variables associated with
    pixelization
    """

    def __init__(self, phase: ph.Phase):
        super().__init__(
            phase=phase,
            variable_classes=(
                px.Pixelization,
                rg.Regularization,
                hd.HyperNoiseBackground
            ),
            default_classes={
                "hyper_noise_background": hd.HyperNoiseBackground
            }
        )


class InversionBackgroundBothPhase(InversionPhase):
    """
    Phase that makes everything in the variable from the previous phase equal to the
    corresponding value from the best fit except for variables associated with
    pixelization
    """

    def __init__(self, phase: ph.Phase):
        super().__init__(
            phase=phase,
            variable_classes=(
                px.Pixelization,
                rg.Regularization,
                hd.HyperImageSky,
                hd.HyperNoiseBackground
            ),
            default_classes={
                "hyper_image_sky": hd.HyperImageSky,
                "hyper_noise_background": hd.HyperNoiseBackground
            }
        )


class HyperGalaxyPhase(HyperPhase):

    def __init__(
            self,
            phase,
            include_sky_background=False,
            include_noise_background=False
    ):
        super().__init__(
            phase=phase,
            hyper_name="hyper_galaxy"
        )
        self.include_sky_background = include_sky_background
        self.include_noise_background = include_noise_background

    class Analysis(af.Analysis):

        def __init__(self, lens_data, model_image_1d, galaxy_image_1d):
            """
            An analysis to fit the noise for a single galaxy image.
            Parameters
            ----------
            lens_data: LensData
                Lens data, including an image and noise
            model_image_1d: ndarray
                An image produce of the overall system by a model
            galaxy_image_1d: ndarray
                The contribution of one galaxy to the model image
            """

            self.lens_data = lens_data

            self.hyper_model_image_1d = model_image_1d
            self.hyper_galaxy_image_1d = galaxy_image_1d

            self.check_for_previously_masked_values(array=self.hyper_model_image_1d)
            self.check_for_previously_masked_values(array=self.hyper_galaxy_image_1d)

            self.plot_hyper_galaxy_subplot = \
                af.conf.instance.visualize.get('plots', 'plot_hyper_galaxy_subplot',
                                               bool)

        @staticmethod
        def check_for_previously_masked_values(array):
            if not np.all(array) != 0.0:
                raise exc.PhaseException(
                    'When mapping a 2D array to a 1D array using lens data, a value '
                    'encountered was 0.0 and therefore masked in a previous phase.')

        def visualize(self, instance, image_path, during_analysis):

            if self.plot_hyper_galaxy_subplot:
                hyper_model_image_2d = self.lens_data.scaled_array_2d_from_array_1d(
                    array_1d=self.hyper_model_image_1d)
                hyper_galaxy_image_2d = self.lens_data.scaled_array_2d_from_array_1d(
                    array_1d=self.hyper_galaxy_image_1d)

                hyper_image_sky = self.hyper_image_sky_for_instance(
                    instance=instance)

                hyper_noise_background = self.hyper_noise_background_for_instance(
                    instance=instance)

                hyper_galaxy = instance.hyper_galaxy

                contribution_map_2d = hyper_galaxy.contribution_map_from_hyper_images(
                    hyper_model_image=hyper_model_image_2d,
                    hyper_galaxy_image=hyper_galaxy_image_2d)

                fit_normal = lens_fit.LensDataFit(
                    image_1d=self.lens_data.image_1d,
                    noise_map_1d=self.lens_data.noise_map_1d,
                    mask_1d=self.lens_data.mask_1d,
                    model_image_1d=self.hyper_model_image_1d,
                    grid_stack=self.lens_data.grid_stack)

                fit = self.fit_for_hyper_galaxy(
                    hyper_galaxy=hyper_galaxy,
                    hyper_image_sky=hyper_image_sky,
                    hyper_noise_background=hyper_noise_background)

                hyper_plotters.plot_hyper_galaxy_subplot(
                    hyper_galaxy_image=hyper_galaxy_image_2d,
                    contribution_map=contribution_map_2d,
                    noise_map=self.lens_data.noise_map(return_in_2d=True),
                    hyper_noise_map=fit.noise_map(return_in_2d=True),
                    chi_squared_map=fit_normal.chi_squared_map(return_in_2d=True),
                    hyper_chi_squared_map=fit.chi_squared_map(return_in_2d=True),
                    output_path=image_path, output_format='png')

        def fit(self, instance):
            """
            Fit the model image to the real image by scaling the hyper noise.
            Parameters
            ----------
            instance: ModelInstance
                A model instance with a hyper galaxy property
            Returns
            -------
            fit: float
            """

            hyper_image_sky = self.hyper_image_sky_for_instance(instance=instance)

            hyper_noise_background = self.hyper_noise_background_for_instance(instance=instance)

            fit = self.fit_for_hyper_galaxy(
                hyper_galaxy=instance.hyper_galaxy,
                hyper_image_sky=hyper_image_sky,
                hyper_noise_background=hyper_noise_background)

            return fit.figure_of_merit

        @staticmethod
        def hyper_image_sky_for_instance(instance):
            if hasattr(instance, 'hyper_image_sky'):
                return instance.hyper_image_sky

        @staticmethod
        def hyper_noise_background_for_instance(instance):
            if hasattr(instance, 'hyper_noise_background'):
                return instance.hyper_noise_background

        def fit_for_hyper_galaxy(self, hyper_galaxy, hyper_image_sky, hyper_noise_background):

            if hyper_image_sky is not None:
                image_1d = hyper_image_sky.image_scaled_sky_from_image(image=self.lens_data.image_1d)
            else:
                image_1d = self.lens_data.image_1d

            if hyper_noise_background is not None:
                noise_map_1d = hyper_noise_background.noise_map_scaled_noise_from_noise_map(
                    noise_map=self.lens_data.noise_map_1d)
            else:
                noise_map_1d = self.lens_data.noise_map_1d

            hyper_noise_1d = hyper_galaxy.hyper_noise_map_from_hyper_images_and_noise_map(
                hyper_model_image=self.hyper_model_image_1d,
                hyper_galaxy_image=self.hyper_galaxy_image_1d,
                noise_map=self.lens_data.noise_map_1d)

            hyper_noise_map_1d = noise_map_1d + hyper_noise_1d

            return lens_fit.LensDataFit(
                image_1d=image_1d,
                noise_map_1d=hyper_noise_map_1d,
                mask_1d=self.lens_data.mask_1d,
                model_image_1d=self.hyper_model_image_1d,
                grid_stack=self.lens_data.grid_stack)

        @classmethod
        def describe(cls, instance):
            return "Running hyper galaxy fit for HyperGalaxy:\n{}".format(
                instance.hyper_galaxy)

    def run_hyper(
            self,
            data,
            results=None,
            mask=None,
            positions=None
    ):
        """
        Run a fit for each galaxy from the previous phase.
        Parameters
        ----------
        data: LensData
        results: ResultsCollection
            Results from all previous phases
        mask: Mask
            The mask
        positions
        Returns
        -------
        results: HyperGalaxyResults
            A collection of results, with one item per a galaxy
        """
        phase = self.make_hyper_phase()

        mask = setup_phase_mask(
            data=data,
            mask=mask,
            mask_function=cast(phase_imaging.PhaseImaging, phase).mask_function,
            inner_mask_radii=cast(phase_imaging.PhaseImaging, phase).inner_mask_radii
        )

        lens_data = ld.LensData(
            ccd_data=data,
            mask=mask,
            sub_grid_size=cast(phase_imaging.PhaseImaging, phase).sub_grid_size,
            image_psf_shape=cast(phase_imaging.PhaseImaging, phase).image_psf_shape,
            positions=positions,
            interp_pixel_scale=cast(phase_imaging.PhaseImaging, phase).interp_pixel_scale,
            cluster_pixel_scale=cast(phase_imaging.PhaseImaging, phase).cluster_pixel_scale,
            cluster_pixel_limit=cast(phase_imaging.PhaseImaging, phase).cluster_pixel_limit,
            uses_inversion=cast(phase_imaging.PhaseImaging, phase).uses_inversion,
            uses_cluster_inversion=cast(phase_imaging.PhaseImaging, phase).uses_cluster_inversion
        )

        model_image_1d = results.last.hyper_model_image_1d_from_mask(mask=lens_data.mask_2d)
        hyper_galaxy_image_1d_path_dict = \
            results.last.hyper_galaxy_image_1d_path_dict_from_mask(mask=lens_data.mask_2d)

        hyper_result = copy.deepcopy(results.last)
        hyper_result.analysis.uses_hyper_images = True
        hyper_result.analysis.hyper_model_image_1d = model_image_1d
        hyper_result.analysis.hyper_galaxy_image_1d_path_dict = hyper_galaxy_image_1d_path_dict

        for path, galaxy in results.last.path_galaxy_tuples:

            optimizer = phase.optimizer.copy_with_name_extension(
                extension=path[-1]
            )

            optimizer.phase_tag = ''

            # TODO : This is a HACK :O

            optimizer.variable.lens_galaxies = []
            optimizer.variable.source_galaxies = []
            optimizer.variable.galaxies = []

            phase.const_efficiency_mode = af.conf.instance.non_linear.get(
                'MultiNest',
                'extension_hyper_galaxy_const_efficiency_mode',
                bool
            )
            phase.optimizer.sampling_efficiency = af.conf.instance.non_linear.get(
                'MultiNest',
                'extension_hyper_galaxy_sampling_efficiency',
                float
            )
            phase.optimizer.n_live_points = af.conf.instance.non_linear.get(
                'MultiNest',
                'extension_hyper_galaxy_n_live_points',
                int
            )

            optimizer.variable.hyper_galaxy = g.HyperGalaxy

            if self.include_sky_background:
                optimizer.variable.hyper_image_sky = hd.HyperImageSky

            if self.include_noise_background:
                optimizer.variable.hyper_noise_background = hd.HyperNoiseBackground

            # If array is all zeros, galaxy did not have image in previous phase and
            # should be ignored
            if not np.all(hyper_galaxy_image_1d_path_dict[path] == 0):

                analysis = self.Analysis(
                    lens_data=lens_data,
                    model_image_1d=model_image_1d,
                    galaxy_image_1d=hyper_galaxy_image_1d_path_dict[path])

                result = optimizer.fit(analysis)

                hyper_result.constant.object_for_path(path).hyper_galaxy = result.constant.hyper_galaxy

                if self.include_sky_background:
                    hyper_result.constant.object_for_path(
                        path).hyper_image_sky = result.constant.hyper_image_sky

                if self.include_noise_background:
                    hyper_result.constant.object_for_path(
                        path).hyper_noise_background = result.constant.hyper_noise_background

        return hyper_result


class CombinedHyperPhase(HyperPhase):
    def __init__(
            self,
            phase: phase_imaging.PhaseImaging,
            hyper_phase_classes: (type,) = tuple()
    ):
        """
        A combined hyper phase that can run zero or more other hyper phases after the initial phase is run.

        Parameters
        ----------
        phase : phase_imaging.PhaseImaging
            The phase wrapped by this hyper phase
        hyper_phase_classes
            The classes of hyper phases to be run following the initial phase
        """
        super().__init__(
            phase,
            "combined"
        )
        self.hyper_phases = list(map(
            lambda cls: cls(phase),
            hyper_phase_classes
        ))

    @property
    def phase_names(self) -> [str]:
        """
        The names of phases included in this combined phase
        """
        return [
            phase.hyper_name
            for phase
            in self.hyper_phases
        ]

    def run(self, data, results: af.ResultsCollection = None, **kwargs) -> af.Result:
        """
        Run the regular phase followed by the hyper phases. Each result of a hyper phase is attached to the
        overall result object by the hyper_name of that phase.

        Finally, a phase in run with all of the variable results from all the individual hyper phases.

        Parameters
        ----------
        data
            The data
        results
            Results from previous phases
        kwargs

        Returns
        -------
        result
            The result of the regular phase, with hyper results attached by associated hyper names
        """
        results = copy.deepcopy(results) if results is not None else af.ResultsCollection()
        result = self.phase.run(data, results=results, **kwargs)
        results.add(self.phase.phase_name, result)

        for hyper_phase in self.hyper_phases:
            hyper_result = hyper_phase.run_hyper(
                data=data,
                results=results,
                **kwargs
            )
            setattr(result, hyper_phase.hyper_name, hyper_result)

        setattr(
            result,
            self.hyper_name,
            self.run_hyper(
                data,
                results
            )
        )
        return result

    def combine_variables(self, result) -> af.ModelMapper:
        """
        Combine the variable objects from all previous results in this combined hyper phase.

        Iterates through the hyper names of the included hyper phases, extracting a result
        for each name and adding the variable of that result to a new variable.

        Parameters
        ----------
        result
            The last result (with attribute results associated with phases in this phase)

        Returns
        -------
        combined_variable
            A variable object including all variables from results in this phase.
        """
        variable = af.ModelMapper()
        for name in self.phase_names:
            variable += getattr(result, name).variable
        return variable

    def run_hyper(self, data, results, **kwargs) -> af.Result:
        variable = self.combine_variables(
            results.last
        )

        phase = self.make_hyper_phase()
        phase.optimizer.phase_tag = ''
        phase.optimizer.variable = variable

        phase.phase_tag = ''
        phase.optimizer.phase_tag = ''

        return phase.run(data, results=results, **kwargs)