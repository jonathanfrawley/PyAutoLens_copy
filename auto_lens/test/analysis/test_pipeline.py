from auto_lens.analysis import pipeline
from auto_lens.analysis import galaxy_prior
from auto_lens.analysis import model_mapper as mm
import pytest
import os


@pytest.fixture(name='test_config')
def make_test_config():
    return mm.Config(
        config_folder_path="{}/../{}".format(os.path.dirname(os.path.realpath(__file__)), "test_files/config"))


class MockImage:
    pass


class MockPixelization:
    pass


class MockPrior:
    pass


class MockPriorModel:
    def __init__(self, name, cls):
        self.name = name
        self.cls = cls
        self.centre = "centre for {}".format(name)
        self.phi = "phi for {}".format(name)


class MockModelInstance:
    pass


@pytest.fixture(name="lens_galaxy_prior")
def make_lens_galaxy_prior():
    return galaxy_prior.GalaxyPrior()


@pytest.fixture(name="source_galaxy_prior")
def make_source_galaxy_prior():
    return galaxy_prior.GalaxyPrior()


@pytest.fixture(name="model_mapper")
def make_model_mapper(test_config):
    return mm.ModelMapper(config=test_config)


@pytest.fixture(name="non_linear_optimizer")
def make_non_linear_optimizer():
    return MockNLO()


@pytest.fixture(name="model_analysis")
def make_model_analysis(lens_galaxy_prior, source_galaxy_prior, model_mapper, non_linear_optimizer, analyse):
    return pipeline.ModelAnalysis(image=MockImage(), lens_galaxy_priors=[lens_galaxy_prior],
                                  source_galaxy_priors=[source_galaxy_prior], pixelization=MockPixelization(),
                                  model_mapper=model_mapper, non_linear_optimizer=non_linear_optimizer,
                                  likelihood_for_tracer=analyse.likelihood_for_tracer)


@pytest.fixture(name="analyse")
def make_analyse():
    return MockAnalyse()


class MockNLO:
    def __init__(self):
        self.priors = None
        self.fitness_function = None

    def run(self, fitness_function, priors):
        self.fitness_function = fitness_function
        self.priors = priors
        fitness_function([0.5, 0.5])


class MockAnalyse:
    # noinspection PyMethodMayBeStatic,PyUnusedLocal
    def likelihood_for_tracer(self, tracer):
        return 1


class TestModelAnalysis:
    def test_setup(self, lens_galaxy_prior, source_galaxy_prior, model_mapper, analyse):
        pipeline.ModelAnalysis(image=MockImage(), lens_galaxy_priors=[lens_galaxy_prior],
                               source_galaxy_priors=[source_galaxy_prior], pixelization=MockPixelization(),
                               model_mapper=model_mapper, non_linear_optimizer=MockNLO(),
                               likelihood_for_tracer=analyse.likelihood_for_tracer)

        assert len(model_mapper.prior_models) == 2

    def test_run(self, model_analysis, non_linear_optimizer):
        result = model_analysis.run()
        assert len(non_linear_optimizer.priors) == 2

        assert result.likelihood == 1
        assert result.lens_galaxies[0].redshift == 0.5
        assert result.source_galaxies[0].redshift == 0.5
