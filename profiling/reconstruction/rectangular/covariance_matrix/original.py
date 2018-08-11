from profiling import profiling_data
from profiling import tools
from analysis import ray_tracing
from analysis import galaxy
from profiles import mass_profiles
from pixelization import pixelization
from autolens import exc
import numpy as np
import pytest
import numba

class Reconstructor(object):

    def __init__(self, mapping, regularization, image_to_pix, sub_to_pix):
        """The matrices and mappings used to linearly invert and fit a data-set.

        Parameters
        -----------
        mapping : ndarray
            The matrix representing the mapping between reconstruction-pixels and weighted_data-pixels.
        regularization : ndarray
            The matrix defining how the reconstruction's pixels are regularized with one another when fitting the
            weighted_data.
        image_to_pix : ndarray
            The mapping between each masked_image-grid pixel and pixelization-grid pixel.
        sub_to_pix : ndarray
            The mapping between each sub-grid pixel and pixelization-grid sub-pixel.
        """
        self.mapping = mapping
        self.mapping_shape = mapping.shape
        self.regularization = regularization
        self.image_to_pix = image_to_pix
        self.sub_to_pix = sub_to_pix

    def covariance_matrix_from_blurred_mapping(self, blurred_mapping, noise_vector):
        """ Compute the covariance matrix directly - used to integration test that our covariance matrix generator approach
        truly works."""

        covariance_matrix = np.zeros((self.mapping_shape[1], self.mapping_shape[1]))

        for i in range(self.mapping_shape[0]):
            for jx in range(self.mapping_shape[1]):
                for jy in range(self.mapping_shape[1]):
                    covariance_matrix[jx, jy] += blurred_mapping[i, jx] * blurred_mapping[i, jy] \
                                                 / (noise_vector[i] ** 2.0)

        return covariance_matrix

sub_grid_size = 4
psf_size = (41, 41)

sie = mass_profiles.EllipticalIsothermal(centre=(0.010, 0.032), einstein_radius=1.47, axis_ratio=0.849, phi=73.6)
shear = mass_profiles.ExternalShear(magnitude=0.0663, phi=160.5)
lens_galaxy = galaxy.Galaxy(mass_profile_0=sie, mass_profile_1=shear)

source_pix = galaxy.Galaxy(pixelization=pixelization.RectangularRegConst(shape=(19, 19)))

lsst = profiling_data.setup_class(name='LSST', pixel_scale=0.2, sub_grid_size=sub_grid_size, psf_shape=psf_size)
euclid = profiling_data.setup_class(name='Euclid', pixel_scale=0.1, sub_grid_size=sub_grid_size, psf_shape=psf_size)
hst = profiling_data.setup_class(name='HST', pixel_scale=0.05, sub_grid_size=sub_grid_size, psf_shape=psf_size)
hst_up = profiling_data.setup_class(name='HSTup', pixel_scale=0.03, sub_grid_size=sub_grid_size, psf_shape=psf_size)
# ao = profiling_data.setup_class(name='AO', pixel_scale=0.01, sub_grid_size=sub_grid_size, psf_shape=psf_size)

lsst_tracer = ray_tracing.Tracer(lens_galaxies=[lens_galaxy], source_galaxies=[source_pix], image_plane_grids=lsst.grids)
euclid_tracer = ray_tracing.Tracer(lens_galaxies=[lens_galaxy], source_galaxies=[source_pix], image_plane_grids=euclid.grids)
hst_tracer = ray_tracing.Tracer(lens_galaxies=[lens_galaxy], source_galaxies=[source_pix], image_plane_grids=hst.grids)
hst_up_tracer = ray_tracing.Tracer(lens_galaxies=[lens_galaxy], source_galaxies=[source_pix], image_plane_grids=hst_up.grids)
# ao_tracer = ray_tracing.Tracer(lens_galaxies=[lens_galaxy], source_galaxies=[source_pix], image_plane_grids=ao.grids)

lsst_recon = lsst_tracer.reconstructors_from_source_plane(lsst.borders, cluster_mask=None)
euclid_recon = euclid_tracer.reconstructors_from_source_plane(euclid.borders, cluster_mask=None)
hst_recon = hst_tracer.reconstructors_from_source_plane(hst.borders, cluster_mask=None)
hst_up_recon = hst_up_tracer.reconstructors_from_source_plane(hst_up.borders, cluster_mask=None)
# ao_recon = ao_tracer.reconstructors_from_source_plane(ao.borders, cluster_mask=None)

lsst_recon = Reconstructor(lsst_recon.mapping, lsst_recon.regularization, lsst_recon.image_to_pix,
                           lsst_recon.sub_to_pix)
euclid_recon = Reconstructor(euclid_recon.mapping, euclid_recon.regularization, euclid_recon.image_to_pix,
                           euclid_recon.sub_to_pix)
hst_recon = Reconstructor(hst_recon.mapping, hst_recon.regularization, hst_recon.image_to_pix,
                           hst_recon.sub_to_pix)
hst_up_recon = Reconstructor(hst_up_recon.mapping, hst_up_recon.regularization, hst_up_recon.image_to_pix,
                           hst_up_recon.sub_to_pix)
# ao_recon = Reconstructor(ao_recon.mapping, ao_recon.regularization, ao_recon.image_to_pix,
#                            ao_recon.sub_to_pix)

lsst_blurred_mapping = lsst.masked_image.convolver_mapping_matrix.convolve_mapping_matrix_jit(lsst_recon.mapping)
euclid_blurred_mapping = euclid.masked_image.convolver_mapping_matrix.convolve_mapping_matrix_jit(euclid_recon.mapping)
hst_blurred_mapping = hst.masked_image.convolver_mapping_matrix.convolve_mapping_matrix_jit(hst_recon.mapping)
hst_up_blurred_mapping = hst_up.masked_image.convolver_mapping_matrix.convolve_mapping_matrix_jit(hst_up_recon.mapping)
# ao_blurred_mapping = ao.masked_image.convolver_mapping_matrix.convolve_mapping_matrix_jit(ao_recon.mapping)

@tools.tick_toc_x1
def lsst_solution():
    lsst_recon.covariance_matrix_from_blurred_mapping(lsst_blurred_mapping, lsst.masked_image.estimated_noise)

@tools.tick_toc_x1
def euclid_solution():
    euclid_recon.covariance_matrix_from_blurred_mapping(euclid_blurred_mapping, euclid.masked_image.estimated_noise)

@tools.tick_toc_x1
def hst_solution():
    hst_recon.covariance_matrix_from_blurred_mapping(hst_blurred_mapping, hst.masked_image.estimated_noise)

@tools.tick_toc_x1
def hst_up_solution():
    hst_up_recon.covariance_matrix_from_blurred_mapping(hst_up_blurred_mapping, hst_up.masked_image.estimated_noise)

@tools.tick_toc_x1
def ao_solution():
    ao_recon.covariance_matrix_from_blurred_mapping_jit(ao_blurred_mapping, ao.masked_image.estimated_noise)

if __name__ == "__main__":
    lsst_solution()
    euclid_solution()
    hst_solution()
    hst_up_solution()
    ao_solution()