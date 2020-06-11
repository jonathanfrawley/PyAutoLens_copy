from os import path

import autolens as al
import numpy as np
import pytest
from test_autolens.mock import mock_pipeline

pytestmark = pytest.mark.filterwarnings(
    "ignore:Using a non-tuple sequence for multidimensional indexing is deprecated; use `arr[tuple(seq)]` instead of "
    "`arr[seq]`. In the future this will be interpreted as an arrays index, `arr[np.arrays(seq)]`, which will result "
    "either in an error or a different result."
)

directory = path.dirname(path.realpath(__file__))


class TestResult:
    def test__results_of_phase_include_mask__available_as_property(
        self, imaging_7x7, mask_7x7
    ):

        phase_imaging_7x7 = al.PhaseImaging(
            phase_name="test_phase",
            galaxies=[
                al.Galaxy(redshift=0.5, light=al.lp.EllipticalSersic(intensity=1.0))
            ],
            settings=al.PhaseSettingsImaging(sub_size=2),
            search=mock_pipeline.MockSearch(),
        )

        result = phase_imaging_7x7.run(
            dataset=imaging_7x7, mask=mask_7x7, results=mock_pipeline.MockResults()
        )

        assert (result.mask == mask_7x7).all()

    def test__results_of_phase_include_positions__available_as_property(
        self, imaging_7x7, mask_7x7
    ):

        phase_imaging_7x7 = al.PhaseImaging(
            phase_name="test_phase",
            galaxies=dict(
                galaxy=al.Galaxy(
                    redshift=0.5, light=al.lp.EllipticalSersic(intensity=1.0)
                )
            ),
            search=mock_pipeline.MockSearch(),
        )

        result = phase_imaging_7x7.run(
            dataset=imaging_7x7, mask=mask_7x7, results=mock_pipeline.MockResults()
        )

        assert result.positions == None

        phase_imaging_7x7 = al.PhaseImaging(
            phase_name="test_phase",
            galaxies=dict(
                lens=al.Galaxy(
                    redshift=0.5, light=al.lp.EllipticalSersic(intensity=1.0)
                ),
                source=al.Galaxy(redshift=1.0),
            ),
            settings=al.PhaseSettingsImaging(positions_threshold=1.0),
            search=mock_pipeline.MockSearch(),
        )

        imaging_7x7.positions = al.GridCoordinates([[(1.0, 1.0)]])

        result = phase_imaging_7x7.run(
            dataset=imaging_7x7, mask=mask_7x7, results=mock_pipeline.MockResults()
        )

        assert (result.positions[0] == np.array([1.0, 1.0])).all()

    def test__results_of_phase_include_pixelization__available_as_property(
        self, imaging_7x7, mask_7x7
    ):

        phase_imaging_7x7 = al.PhaseImaging(
            phase_name="test_phase",
            galaxies=dict(
                lens=al.Galaxy(
                    redshift=0.5, light=al.lp.EllipticalSersic(intensity=1.0)
                ),
                source=al.Galaxy(
                    redshift=1.0,
                    pixelization=al.pix.VoronoiMagnification(shape=(2, 3)),
                    regularization=al.reg.Constant(),
                ),
            ),
            settings=al.PhaseSettingsImaging(inversion_pixel_limit=6),
            search=mock_pipeline.MockSearch(),
        )

        result = phase_imaging_7x7.run(
            dataset=imaging_7x7, mask=mask_7x7, results=mock_pipeline.MockResults()
        )

        assert isinstance(result.pixelization, al.pix.VoronoiMagnification)
        assert result.pixelization.shape == (2, 3)

        phase_imaging_7x7 = al.PhaseImaging(
            phase_name="test_phase",
            galaxies=dict(
                lens=al.Galaxy(
                    redshift=0.5, light=al.lp.EllipticalSersic(intensity=1.0)
                ),
                source=al.Galaxy(
                    redshift=1.0,
                    pixelization=al.pix.VoronoiBrightnessImage(pixels=6),
                    regularization=al.reg.Constant(),
                ),
            ),
            settings=al.PhaseSettingsImaging(inversion_pixel_limit=6),
            search=mock_pipeline.MockSearch(),
        )

        phase_imaging_7x7.galaxies.source.hyper_galaxy_image = np.ones(9)

        result = phase_imaging_7x7.run(
            dataset=imaging_7x7, mask=mask_7x7, results=mock_pipeline.MockResults()
        )

        assert isinstance(result.pixelization, al.pix.VoronoiBrightnessImage)
        assert result.pixelization.pixels == 6

    def test__results_of_phase_include_pixelization_grid__available_as_property(
        self, imaging_7x7, mask_7x7
    ):

        phase_imaging_7x7 = al.PhaseImaging(
            phase_name="test_phase_2",
            galaxies=dict(
                galaxy=al.Galaxy(
                    redshift=0.5, light=al.lp.EllipticalSersic(intensity=1.0)
                )
            ),
            search=mock_pipeline.MockSearch(),
        )

        result = phase_imaging_7x7.run(
            dataset=imaging_7x7, mask=mask_7x7, results=mock_pipeline.MockResults()
        )

        assert result.max_log_likelihood_pixelization_grids_of_planes == [None]

        phase_imaging_7x7 = al.PhaseImaging(
            phase_name="test_phase_2",
            galaxies=dict(
                lens=al.Galaxy(
                    redshift=0.5, light=al.lp.EllipticalSersic(intensity=1.0)
                ),
                source=al.Galaxy(
                    redshift=1.0,
                    pixelization=al.pix.VoronoiBrightnessImage(pixels=6),
                    regularization=al.reg.Constant(),
                ),
            ),
            settings=al.PhaseSettingsImaging(inversion_pixel_limit=6),
            search=mock_pipeline.MockSearch(),
        )

        phase_imaging_7x7.galaxies.source.hyper_galaxy_image = np.ones(9)

        result = phase_imaging_7x7.run(
            dataset=imaging_7x7, mask=mask_7x7, results=mock_pipeline.MockResults()
        )

        assert result.max_log_likelihood_pixelization_grids_of_planes[-1].shape == (
            6,
            2,
        )
