import numpy as np
import pytest
import tensorflow as tf
import tensorflow_probability as tfp

from probflow.parameters import Parameter
from probflow.utils.base import BaseDistribution
from probflow.utils.settings import Sampling

tfd = tfp.distributions


def is_close(a, b, tol=1e-3):
    return np.abs(a - b) < tol


def test_Parameter_scalar():
    """Tests the generic scalar Parameter"""

    # Create scalar parameter
    param = Parameter()

    # Check defaults
    assert isinstance(param.shape, list)
    assert param.shape[0] == 1
    assert isinstance(param.untransformed_variables, dict)
    assert all(isinstance(p, str) for p in param.untransformed_variables)
    assert all(
        isinstance(p, tf.Variable)
        for _, p in param.untransformed_variables.items()
    )

    # Shape should be >0
    with pytest.raises(ValueError):
        Parameter(shape=-1)
    with pytest.raises(ValueError):
        Parameter(shape=[20, 0, 1])

    # trainable_variables should be a property returning list of vars
    assert all(isinstance(v, tf.Variable) for v in param.trainable_variables)

    # variables should be a property returning dict of transformed vars
    assert isinstance(param.variables, dict)
    assert all(isinstance(v, str) for v in param.variables)

    # loc should be variable, while scale should have been transformed->tensor
    assert isinstance(param.variables["loc"], tf.Variable)
    assert isinstance(param.variables["scale"], tf.Tensor)

    # posterior should be a distribution object
    assert isinstance(param.posterior, BaseDistribution)
    assert isinstance(param.posterior(), tfd.Normal)

    # __call__ should return the MAP estimate by default
    sample1 = param()
    sample2 = param()
    assert sample1.ndim == 1
    assert sample2.ndim == 1
    assert sample1.shape[0] == 1
    assert sample2.shape[0] == 1
    assert sample1.numpy() == sample2.numpy()

    # within a Sampling statement, should randomly sample from the dist
    with Sampling(n=1):
        sample1 = param()
        sample2 = param()
    assert sample1.ndim == 1
    assert sample2.ndim == 1
    assert sample1.shape[0] == 1
    assert sample2.shape[0] == 1
    assert sample1.numpy() != sample2.numpy()

    # sampling statement should effect N samples
    with Sampling(n=10):
        sample1 = param()
        sample2 = param()
    assert sample1.ndim == 2
    assert sample2.ndim == 2
    assert sample1.shape[0] == 10
    assert sample1.shape[1] == 1
    assert sample2.shape[0] == 10
    assert sample2.shape[1] == 1
    assert np.all(sample1.numpy() != sample2.numpy())

    # sampling statement should allow static samples
    sample1 = param()
    with Sampling(static=True):
        with Sampling(n=1):
            sample2 = param()
            sample3 = param()
    with Sampling(static=True):
        with Sampling(n=1):
            sample4 = param()
            sample5 = param()
    assert sample1.ndim == 1
    assert sample2.ndim == 1
    assert sample3.ndim == 1
    assert sample4.ndim == 1
    assert sample5.ndim == 1
    assert sample1.shape[0] == 1
    assert sample2.shape[0] == 1
    assert sample3.shape[0] == 1
    assert sample4.shape[0] == 1
    assert sample5.shape[0] == 1
    assert sample1.numpy() != sample2.numpy()
    assert sample1.numpy() != sample3.numpy()
    assert sample2.numpy() == sample3.numpy()
    assert sample1.numpy() != sample4.numpy()
    assert sample1.numpy() != sample5.numpy()
    assert sample4.numpy() == sample5.numpy()
    assert sample2.numpy() != sample4.numpy()

    # sampling statement should allow static samples (and work w/ n>1)
    with Sampling(static=True):
        with Sampling(n=5):
            sample1 = param()
            sample2 = param()
    with Sampling(static=True):
        with Sampling(n=5):
            sample3 = param()
            sample4 = param()
    assert sample1.ndim == 2
    assert sample2.ndim == 2
    assert sample3.ndim == 2
    assert sample4.ndim == 2
    assert sample1.shape[0] == 5
    assert sample1.shape[1] == 1
    assert sample2.shape[0] == 5
    assert sample2.shape[1] == 1
    assert sample3.shape[0] == 5
    assert sample3.shape[1] == 1
    assert sample4.shape[0] == 5
    assert sample4.shape[1] == 1
    assert np.all(sample1.numpy() == sample2.numpy())
    assert np.all(sample1.numpy() != sample3.numpy())
    assert np.all(sample1.numpy() != sample4.numpy())
    assert np.all(sample2.numpy() != sample3.numpy())
    assert np.all(sample2.numpy() != sample4.numpy())
    assert np.all(sample3.numpy() == sample4.numpy())

    # kl_loss should return sum of kl divergences
    kl_loss = param.kl_loss()
    assert isinstance(kl_loss, tf.Tensor)
    assert kl_loss.ndim == 0

    # prior_sample should be 1D
    prior_sample = param.prior_sample()
    assert prior_sample.ndim == 0
    prior_sample = param.prior_sample(n=7)
    assert prior_sample.ndim == 1
    assert prior_sample.shape[0] == 7

    # prior and posterior shouldn't be the same (post was randomly initialized)
    assert tf.reduce_all(param.prior.loc != param.posterior.loc).numpy()
    assert tf.reduce_all(param.prior.scale != param.posterior.scale).numpy()

    # but they should be the same after running bayesian_update
    param.bayesian_update()
    assert tf.reduce_all(param.prior.loc == param.posterior.loc).numpy()
    assert tf.reduce_all(param.prior.scale == param.posterior.scale).numpy()


def test_Parameter_no_prior():
    """Tests a parameter with no prior"""

    # Create parameter with no prior
    param = Parameter(prior=None)

    # kl_loss should return 0
    kl_loss = param.kl_loss()
    assert isinstance(kl_loss, tf.Tensor)
    assert kl_loss.ndim == 0
    assert kl_loss.numpy() == 0.0

    # prior_sample should return nans with prior=None
    prior_sample = param.prior_sample()
    assert prior_sample.ndim == 1
    assert prior_sample.shape[0] == 1
    assert np.all(np.isnan(prior_sample))
    prior_sample = param.prior_sample(n=7)
    assert prior_sample.ndim == 1
    assert prior_sample.shape[0] == 7
    assert np.all(np.isnan(prior_sample))


def test_Parameter_1D():
    """Tests a 1D Parameter"""

    # Create 1D parameter
    param = Parameter(shape=5)

    # kl_loss should still be scalar
    kl_loss = param.kl_loss()
    assert isinstance(kl_loss, tf.Tensor)
    assert kl_loss.ndim == 0

    # posterior_mean should return mean
    sample1 = param.posterior_mean()
    sample2 = param.posterior_mean()
    assert sample1.ndim == 1
    assert sample2.ndim == 1
    assert sample1.shape[0] == 5
    assert sample2.shape[0] == 5
    assert np.all(sample1 == sample2)

    # posterior_sample should return samples
    sample1 = param.posterior_sample()
    sample2 = param.posterior_sample()
    assert sample1.ndim == 1
    assert sample2.ndim == 1
    assert sample1.shape[0] == 5
    assert sample2.shape[0] == 5
    assert np.all(sample1 != sample2)

    # posterior_sample should be able to return multiple samples
    sample1 = param.posterior_sample(10)
    sample2 = param.posterior_sample(10)
    assert sample1.ndim == 2
    assert sample2.ndim == 2
    assert sample1.shape[0] == 10
    assert sample1.shape[1] == 5
    assert sample2.shape[0] == 10
    assert sample2.shape[1] == 5
    assert np.all(sample1 != sample2)

    # prior_sample should still be 1D
    prior_sample = param.prior_sample()
    assert prior_sample.ndim == 0
    prior_sample = param.prior_sample(n=7)
    assert prior_sample.ndim == 1
    assert prior_sample.shape[0] == 7

    # n_parameters property
    nparams = param.n_parameters
    assert isinstance(nparams, int)
    assert nparams == 5


def test_Parameter_2D():
    """Tests a 2D Parameter"""

    # Create 1D parameter
    param = Parameter(shape=[5, 4], name="lala")

    # repr
    pstr = param.__repr__()
    assert pstr == "<pf.Parameter lala shape=[5, 4]>"

    # kl_loss should still be scalar
    kl_loss = param.kl_loss()
    assert isinstance(kl_loss, tf.Tensor)
    assert kl_loss.ndim == 0

    # posterior_mean should return mean
    sample1 = param.posterior_mean()
    sample2 = param.posterior_mean()
    assert sample1.ndim == 2
    assert sample2.ndim == 2
    assert sample1.shape[0] == 5
    assert sample1.shape[1] == 4
    assert sample2.shape[0] == 5
    assert sample2.shape[1] == 4
    assert np.all(sample1 == sample2)

    # posterior_sample should return samples
    sample1 = param.posterior_sample()
    sample2 = param.posterior_sample()
    assert sample1.ndim == 2
    assert sample2.ndim == 2
    assert sample1.shape[0] == 5
    assert sample1.shape[1] == 4
    assert sample2.shape[0] == 5
    assert sample2.shape[1] == 4
    assert np.all(sample1 != sample2)

    # posterior_sample should be able to return multiple samples
    sample1 = param.posterior_sample(10)
    sample2 = param.posterior_sample(10)
    assert sample1.ndim == 3
    assert sample2.ndim == 3
    assert sample1.shape[0] == 10
    assert sample1.shape[1] == 5
    assert sample1.shape[2] == 4
    assert sample2.shape[0] == 10
    assert sample2.shape[1] == 5
    assert sample2.shape[2] == 4
    assert np.all(sample1 != sample2)

    # prior_sample should still be 1D
    prior_sample = param.prior_sample()
    assert prior_sample.ndim == 0
    prior_sample = param.prior_sample(n=7)
    assert prior_sample.ndim == 1
    assert prior_sample.shape[0] == 7

    # n_parameters property
    nparams = param.n_parameters
    assert isinstance(nparams, int)
    assert nparams == 20


def test_Parameter_slicing():
    """Tests a slicing Parameters"""

    # Create 1D parameter
    param = Parameter(shape=[2, 3, 4, 5])

    # Should be able to slice!
    sl = param[0].numpy()
    assert sl.ndim == 4
    assert sl.shape[0] == 1
    assert sl.shape[1] == 3
    assert sl.shape[2] == 4
    assert sl.shape[3] == 5

    sl = param[:, :, :, :2].numpy()
    assert sl.ndim == 4
    assert sl.shape[0] == 2
    assert sl.shape[1] == 3
    assert sl.shape[2] == 4
    assert sl.shape[3] == 2

    sl = param[1, ..., :2].numpy()
    assert sl.ndim == 4
    assert sl.shape[0] == 1
    assert sl.shape[1] == 3
    assert sl.shape[2] == 4
    assert sl.shape[3] == 2

    sl = param[...].numpy()
    assert sl.ndim == 4
    assert sl.shape[0] == 2
    assert sl.shape[1] == 3
    assert sl.shape[2] == 4
    assert sl.shape[3] == 5

    sl = param[tf.constant([0]), :, ::2, :].numpy()
    assert sl.ndim == 4
    assert sl.shape[0] == 1
    assert sl.shape[1] == 3
    assert sl.shape[2] == 2
    assert sl.shape[3] == 5


def test_Parameter_posterior_ci():
    """Tests probflow.parameters.Parameter.posterior_ci"""

    # With a scalar parameter
    param = Parameter()
    lb, ub = param.posterior_ci()
    assert isinstance(lb, np.ndarray)
    assert isinstance(ub, np.ndarray)
    assert lb.ndim == 1
    assert ub.ndim == 1
    assert lb.shape[0] == 1
    assert ub.shape[0] == 1

    # Should error w/ invalid ci or n vals
    with pytest.raises(ValueError):
        lb, ub = param.posterior_ci(ci=-0.1)
    with pytest.raises(ValueError):
        lb, ub = param.posterior_ci(ci=1.1)
    with pytest.raises(ValueError):
        lb, ub = param.posterior_ci(n=0)

    # With a 1D parameter
    param = Parameter(shape=5)
    lb, ub = param.posterior_ci()
    assert isinstance(lb, np.ndarray)
    assert isinstance(ub, np.ndarray)
    assert lb.ndim == 1
    assert ub.ndim == 1
    assert lb.shape[0] == 5
    assert ub.shape[0] == 5

    # With a 2D parameter
    param = Parameter(shape=[5, 4])
    lb, ub = param.posterior_ci()
    assert isinstance(lb, np.ndarray)
    assert isinstance(ub, np.ndarray)
    assert lb.ndim == 2
    assert ub.ndim == 2
    assert lb.shape[0] == 5
    assert lb.shape[1] == 4
    assert ub.shape[0] == 5
    assert ub.shape[1] == 4


def test_Parameter_float_initializer():
    """Tests a 2D Parameter with a float initializer"""

    # Create 1D parameter
    param = Parameter(
        shape=[5, 4], name="lala2", initializer={"loc": 1.0, "scale": 2.0}
    )

    # all should have been initialized to 1
    vals = param()
    assert np.all(vals == 1.0)
