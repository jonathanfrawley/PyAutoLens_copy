import numpy as np

from autolens.data.array import grids
from autolens.data.ccd import ccd as im
from autolens.data.ccd import convolution
from autolens.data.array import mask as msk
from autolens.model.inversion import convolution as inversion_convolution


class LensImage(object):

    def __init__(self, ccd, mask, sub_grid_size=2, image_psf_shape=None, mapping_matrix_psf_shape=None,
                 positions=None):
        """
        The lens image is the collection of datas (image, noise-map, PSF), a masks, grid_stacks, convolvers \
        and other utilities that are used for modeling and fitting an image of a strong lens.

        Whilst the image datas is initially loaded in 2D, for the lens image the masked-image (and noise-map) \
        are reduced to 1D arrays for faster calculations.

        Parameters
        ----------
        ccd: im.CCD
            The ccd data all in 2D (the image, noise-map, PSF, etc.)
        mask: msk.Mask
            The 2D masks that is applied to the image.
        sub_grid_size : int
            The size of the sub-grid used for each lens SubGrid. E.g. a value of 2 grid_stacks each image-pixel on a 2x2 \
            sub-grid.
        image_psf_shape : (int, int)
            The shape of the PSF used for convolving model image generated using analytic light profiles. A smaller \
            shape will trim the PSF relative to the input image PSF, giving a faster analysis run-time.
        mapping_matrix_psf_shape : (int, int)
            The shape of the PSF used for convolving the inversion mapping matrix. A smaller \
            shape will trim the PSF relative to the input image PSF, giving a faster analysis run-time.
        positions : [[]]
            Lists of image-pixel coordinates (arc-seconds) that mappers close to one another in the source-plane(s), \
            used to speed up the non-linear sampling.
        """

        self.ccd = ccd

        self.image = ccd.image
        self.noise_map = ccd.noise_map
        self.pixel_scale = ccd.pixel_scale
        self.psf = ccd.psf

        self.mask = mask

        self.image_1d = mask.map_2d_array_to_masked_1d_array(array_2d=ccd.image)
        self.noise_map_1d = mask.map_2d_array_to_masked_1d_array(array_2d=ccd.noise_map)
        self.mask_1d = mask.map_2d_array_to_masked_1d_array(array_2d=mask)

        self.sub_grid_size = sub_grid_size

        if image_psf_shape is None:
            image_psf_shape = self.psf.shape

        self.convolver_image = convolution.ConvolverImage(mask=self.mask,
                                        blurring_mask=mask.blurring_mask_for_psf_shape(psf_shape=image_psf_shape),
                                        psf=self.psf.resized_scaled_array_from_array(new_shape=image_psf_shape))

        if mapping_matrix_psf_shape is None:
            mapping_matrix_psf_shape = self.psf.shape

        self.convolver_mapping_matrix = inversion_convolution.ConvolverMappingMatrix(self.mask,
                      self.psf.resized_scaled_array_from_array(mapping_matrix_psf_shape))

        self.grid_stack = grids.GridStack.grid_stack_from_mask_sub_grid_size_and_psf_shape(mask=mask,
                                              sub_grid_size=sub_grid_size, psf_shape=image_psf_shape)

        self.padded_grid_stack = grids.GridStack.padded_grid_stack_from_mask_sub_grid_size_and_psf_shape(mask=mask,
                                                            sub_grid_size=sub_grid_size, psf_shape=image_psf_shape)

        self.border = grids.RegularGridBorder.from_mask(mask=mask)

        self.positions = positions

    @property
    def map_to_scaled_array(self):
        return self.grid_stack.regular.scaled_array_from_array_1d

    def __array_finalize__(self, obj):
        if isinstance(obj, LensImage):
            self.image = obj.image
            self.noise_map = obj.noise_map
            self.mask = obj.mask
            self.psf = obj.psf
            self.image_1d = obj.image_1d
            self.noise_map_1d = obj.noise_map_1d
            self.mask_1d = obj.mask_1d
            self.sub_grid_size = obj.sub_grid_size
            self.convolver_image = obj.convolver_image
            self.convolver_mapping_matrix = obj.convolver_mapping_matrix
            self.grid_stack = obj.grid_stack
            self.padded_grid_stack = obj.padded_grid_stack
            self.border = obj.border
            self.positions = obj.positions


class LensHyperImage(LensImage):

    def __init__(self, ccd, mask, hyper_model_image, hyper_galaxy_images, hyper_minimum_values, sub_grid_size=2,
                 image_psf_shape=None, mapping_matrix_psf_shape=None, positions=None):
        """
        The lens image is the collection of datas (image, noise-map, PSF), a masks, grid_stacks, convolvers and other \
        utilities that are used for modeling and fitting an image of a strong lens.

        Whilst the image datas is initially loaded in 2D, for the lens image the masked-image (and noise-map) \
        are reduced to 1D arrays for faster calculations.

        Parameters
        ----------
        ccd: im.CCD
            The ccd data all in 2D (the image, noise-map, PSF, etc.)
        mask: msk.Mask
            The 2D masks that is applied to the image.
        sub_grid_size : int
            The size of the sub-grid used for each lens SubGrid. E.g. a value of 2 grid_stacks each image-pixel on a 2x2 \
            sub-grid.
        image_psf_shape : (int, int)
            The shape of the PSF used for convolving model image generated using analytic light profiles. A smaller \
            shape will trim the PSF relative to the input image PSF, giving a faster analysis run-time.
        mapping_matrix_psf_shape : (int, int)
            The shape of the PSF used for convolving the inversion mapping matrix. A smaller \
            shape will trim the PSF relative to the input image PSF, giving a faster analysis run-time.
        positions : [[]]
            Lists of image-pixel coordinates (arc-seconds) that mappers close to one another in the source-plane(s), used \
            to speed up the non-linear sampling.
        """
        super().__init__(ccd=ccd, mask=mask, sub_grid_size=sub_grid_size, image_psf_shape=image_psf_shape,
                         mapping_matrix_psf_shape=mapping_matrix_psf_shape, positions=positions)

        self.hyper_model_image = hyper_model_image
        self.hyper_galaxy_images = hyper_galaxy_images
        self.hyper_minimum_values = hyper_minimum_values

        self.hyper_model_image_1d = mask.map_2d_array_to_masked_1d_array(array_2d=hyper_model_image)
        self.hyper_galaxy_images_1d = list(map(lambda hyper_galaxy_image :
                                               mask.map_2d_array_to_masked_1d_array(hyper_galaxy_image),
                                               hyper_galaxy_images))

    def __array_finalize__(self, obj):
        super(LensHyperImage, self).__array_finalize__(obj)
        if isinstance(obj, LensHyperImage):
            self.hyper_model_image = obj.hyper_model_image
            self.hyper_galaxy_images = obj.hyper_galaxy_images
            self.hyper_minimum_values = obj.hyper_minimum_values
            self.hyper_model_image_1d = obj.hyper_model_image_1d
            self.hyper_galaxy_images_1d = obj.hyper_galaxy_images_1d