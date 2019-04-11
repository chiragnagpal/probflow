"""Abstract base classes.

The :mod:`.core` module contains abstract base classes (ABCs) for all of
ProbFlow's classes.  In other words, none of the classes in the :mod:`.core` 
module can be instantiated - they only exist to implement functionality 
common to the classes which inherit them.  The :mod:`.core` module includes:

* :obj:`.REQUIRED`, a sentinel object used to indicate required arguments,
* :class:`.BaseObject`, ABC from which all ProbFlow classes inherit,
* :class:`.BaseParameter`, ABC from which all |Parameters| inherit,
* :class:`.BaseLayer`, ABC from which all |Layers| inherit, 
* :class:`.BaseDistribution`, ABC from which all |Distributions| inherit, 
* :class:`.ContinuousDistribution`, a sub-type of distribution for continuous 
  dependent variables (such as the :class:`.Normal` and :class:`.Cauchy`
  distributions), and 
* :class:`.DiscreteDistribution`, a sub-type of distribution for discrete 
  dependent variables (such as the :class:`.Bernoulli` and :class:`.Poisson`
  distributions).

----------

"""



__all__ = [
    'REQUIRED',
    'BaseObject',
    'BaseParameter',
    'BaseLayer',
    'BaseDistribution',
    'ContinuousDistribution',
    'DiscreteDistribution',
]

from abc import ABC, abstractmethod

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import tensorflow as tf
import tensorflow_probability as tfp

from .utils.data import process_data
from .utils.data import process_xy_data
from .utils.data import test_train_split
from .utils.data import initialize_shuffles
from .utils.data import generate_batch
from .utils.plotting import plot_line, plot_dist, fill_between, plot_by



# Sentinel object to represent required arguments
REQUIRED = object()



class BaseObject(ABC):
    """Abstract base class for all ProbFlow objects"""

    def __add__(self, other):
        """Add this layer to a |Layer|, |Parameter|, or |Tensor|."""
        from .layers import Add
        return Add(self, other)


    def __sub__(self, other):
        """Subtract from this layer a |Layer|, |Parameter|, or |Tensor|."""
        from .layers import Sub
        return Sub(self, other)


    def __mul__(self, other):
        """Multiply this layer by a |Layer|, |Parameter|, or |Tensor|."""
        from .layers import Mul
        return Mul(self, other)


    def __truediv__(self, other):
        """Divide this layer by a |Layer|, |Parameter|, or |Tensor|."""
        from .layers import Div
        return Div(self, other)


    def __abs__(self):
        """Take the absolute value of the input to this layer."""
        from .layers import Abs
        return Abs(self)


    def __neg__(self):
        """Take the negative of the input to this layer."""
        from .layers import Neg
        return Neg(self)


    def __matmul__(self, other):
        """Matrix multiply this layer by another, per PEP 465."""
        from .layers import Matmul
        return Matmul(self, other)


    def _validate_kwargs(self, kwargs):
        """Ensure the keyword arguments have correct types, etc."""
        pass



class BaseParameter(BaseObject):
    """Abstract base class for ProbFlow |Parameters| """
    pass



class BaseLayer(BaseObject):
    """Abstract base class for ProbFlow |Layers| 

    This is an abstract base class for |Layers|.  Layers are objects
    which take |Tensors|, |Parameters|, or other |Layers| as input, and output
    a tensor.

    An inheriting class *must* define the following method:

    * ``_build(self, args, data, batch_shape)``

    where:

    * ``args`` is a dict of named arguments to the layer,
    * ``data`` is a |tf.placeholder| containing the dependent variable data,
    * ``batch_shape`` is a list containing the shape of each batch.

    This ``_build`` method must return a |Tensor| which was build from the 
    layer's ``args``, using |TensorFlow| operations.  For example, to
    implement a layer which adds its two inputs, the ``_build`` method 
    should look like::

        def _build(self, args, _data, _batch_shape):
            return tf.add(args['a'], args['b'])

    Usually |Layers| will only operate on their ``args``, and will not use the 
    ``data`` or the ``batch_shape``.  However, those additional arguments are
    needed for some special layers such as :class:`.Input` and 
    :class:`.Dense`.

    Also, an inheriting class may optionally override the following attributes
    and methods:

    * ``_default_args`` - an attribute which stores the default arguments to
      the layer as a dict.  The default is 
      ``{'input': probflow.core.REQUIRED}``.  That is, the default is for a
      layer to require one argument named ``'input'``.
    * ``_default_kwargs`` - an attribute which stores the default *keyword*
      arguments to the layer as a dict.  The default is an empty dict.
      That is, the default is for a layer to take no keyword arguments.
    * ``_build_mean(self, args, data, batch_shape)`` - a method to build the
      "mean" model (the model with all parameter values set to the mean of
      their variational posterior distributions).  Should return a |Tensor|
      containing the input after performing this layer's transformation.
      Default is to perform the same computation as ``_build``.
    * ``_log_loss(self, vals)`` - a method to compute the log loss (the log
      probability) incurred by the layer.  Should return a scalar |Tensor|.
      Default is to return 0.
    * ``_mean_log_loss(self, vals)`` - a method to compute the log loss (the
      log probability) incurred by the layer under the mean model (the model 
      with all parameter values set to the mean of their variational
      posterior distributions). Should return a scalar |Tensor|.
      Default is to return 0.
    * ``_kl_loss(self)`` - a method to compute the Kullback–Leibler divergence
      incurred by the layer.  Should return a scalar |Tensor|.
      Default is to return 0.


    Examples
    --------

    We can define a |Layer| which adds two arguments like so::

        from probflow.core import BaseLayer, REQUIRED

        class Add(BaseLayer):

            _default_args = {
                'a': REQUIRED,
                'b': REQUIRED
            }

            def _build(self, args, data):
                return args['a'] + args['b']

    Then we can use that layer to add two other |Layers| or |Tensors|::

        x = Input()
        b = Parameter()
        mu = Add(x, b)

    For more examples, see the implementations of |Layer| classes
    such as :class:`.Input`, :class:`.Mul`, :class:`.Abs`, :class:`.Sum`, 
    :class:`.Dot`, and :class:`.Dense`.
    """


    # Layer arguments and their default values
    _default_args = {
        'input': REQUIRED
    }


    # Default keyword arguments for a layer
    _default_kwargs = dict()


    def __init__(self, *args, **kwargs):
        """Construct the layer.

        Initializing a layer with this method constructs the layer using 
        the layer's :attr:`._default_args` and :attr:`._default_kwargs`.
        Non-keyword arguments passed to this constructor method will be 
        parsed as the :attr:`._default_args` and will override the values in
        that attribute.  Keyword arguments passed to this constructor method
        will be  parsed as the :attr:`._default_kwargs` and will override the
        corresponding values in that attribute.  


        .. admonition:: |TensorFlow| graph is not built until |Model| is fit!

            Constructing a layer does not build that layer's contribution to
            the |TensorFlow| graph.  This is delayed until 
            :meth:`fit <.BaseDistribution.fit>` is
            called on a |Model| which this |Layer| is a part of.

        """

        # TODO: error if no args and you pass a kwarg w/ no keyword

        # Set layer arguments, using args, kwargs, and defaults
        self.args = dict()
        for ix, arg in enumerate(self._default_args):
            if ix < len(args):
                self.args[arg] = args[ix]
            elif arg in kwargs:
                self.args[arg] = kwargs[arg]
            else:
                self.args[arg] = self._default_args[arg]

        # Ensure all required arguments have been set
        for val in self.args.values():
            if val is REQUIRED:
                raise TypeError('required arg(s) were not set. '+
                                type(self).__name__+' requires args: '+
                                ', '.join(self._default_args.keys()))

        # Ensure all arguments are of correct type
        for arg in self.args:
            if not self._arg_is('valid', self.args[arg]):
                msg = ('Invalid type for ' + type(self).__name__ +
                       ' argument ' + arg +
                       '.  Arguments to a layer must be one of: ' +
                       'int, float, np.ndarray, ' +
                       'tf.Tensor, tf.Variable, ' +
                       'or a probflow layer or parameter.')
                raise TypeError(msg)

        # Set layer kwargs
        self.kwargs = dict()
        for ix, kwarg in enumerate(self._default_kwargs):
            if len(args) > (len(self._default_args)+ix): #leftover args!
                self.kwargs[kwarg] = args[len(args)+ix]
            elif kwarg in kwargs:
                self.kwargs[kwarg] = kwargs[kwarg]
            else:
                self.kwargs[kwarg] = self._default_kwargs[kwarg]
        self._validate_kwargs(self.kwargs)

        # Set attribs for the built layer and fit state
        self.built_obj = None
        self.built_args = None
        self.mean_obj = None
        self.mean_args = None
        self.is_fit = False
        self.log_loss = 0


    @abstractmethod
    def _build(self, args, data, batch_shape):
        """Build layer.

        Inheriting class must define this method performing some computation
        on the input ``args`` using |TensorFlow| operations.  Usually |Layers|
        will only operate on their ``args``, and will not use the ``data`` or
        the ``batch_shape``.  However, those additional arguments are needed
        for some special layers such as :class:`.Input` and  :class:`.Dense`.


        Parameters
        ----------
        args : dict
            Dictionary of named arguments to the layer.  Keys will contain
            names of each argument (str), and each values will be a |Tensor|
            with that argument's value.
        data : |tf.placeholder|
            Dependent variable data for a batch.
        batch_shape : int or list
            Shape of the batch.


        Returns
        -------
        output : |Tensor| or |tfp.distribution|
            The output |Tensor| of the layer after performing the computation
            on its inputs.  If this |Layer| is a |Distribution| , it should
            instead output a |tfp.distribution| .
        """
        pass


    def _build_mean(self, args, data, batch_shape):
        """Build the layer with mean parameters."""
        return self._build(args, data, batch_shape)


    def _log_loss(self, vals):
        """Compute the log loss incurred by this layer."""
        return 0


    def _mean_log_loss(self, vals):
        """Compute the log loss incurred by this layer in the mean model."""
        return 0


    def _kl_loss(self):
        """Compute the loss due to posterior divergence from priors."""
        return 0


    def _arg_is(self, type_str, arg):
        """Return true if arg is of type type_str."""
        if type_str == 'tensor_like':
            return isinstance(arg, (int, float, np.ndarray,
                                    tf.Tensor, tf.Variable))
        elif type_str == 'distribution':
            return isinstance(arg, BaseDistribution)
        elif type_str == 'layer':
            return isinstance(arg, BaseLayer)
        elif type_str == 'parameter':
            return isinstance(arg, BaseParameter)
        elif type_str == 'valid': #valid input to a layer
            return (not isinstance(arg, BaseDistribution) and
                    isinstance(arg, (int, float, np.ndarray,
                                     tf.Tensor, tf.Variable,
                                     BaseLayer, BaseParameter)))
        else:
            raise TypeError('type_str must a string, one of: number, tensor,' +
                            ' tensor_like, model, layer, or valid')


    def _build_recursively(self, data, batch_shape):
        """Recursively build this layer and its arguments and losses"""

        # Build each of this layer's arguments.
        self.built_args = dict()
        self.mean_args = dict()
        for arg_name, arg in self.args.items():
            if isinstance(arg, int):
                self.built_args[arg_name] = float(arg)
                self.mean_args[arg_name] = float(arg)
            elif self._arg_is('tensor_like', arg):
                self.built_args[arg_name] = arg
                self.mean_args[arg_name] = arg
            elif self._arg_is('layer', arg) or self._arg_is('parameter', arg):
                arg._build_recursively(data, batch_shape)
                self.built_args[arg_name] = arg.built_obj
                self.mean_args[arg_name] = arg.mean_obj

        # Sum the losses of this layer's arguments
        self.samp_loss_sum = 0 #log posterior probability of sample model
        self.mean_loss_sum = 0 #log posterior probability of mean model
        self.kl_loss_sum = 0 #sum of KL div between variational post and priors
        for arg_name, arg in self.args.items():
            if self._arg_is('tensor_like', arg):
                pass #no loss incurred by data
            elif self._arg_is('layer', arg):
                self.samp_loss_sum += arg.samp_loss_sum
                self.samp_loss_sum += arg._log_loss(arg.built_obj)
                self.mean_loss_sum += arg.mean_loss_sum
                self.mean_loss_sum += arg._mean_log_loss(arg.mean_obj)
                self.kl_loss_sum += arg.kl_loss_sum + arg._kl_loss()
            elif self._arg_is('parameter', arg):
                self.samp_loss_sum += arg._log_loss
                self.mean_loss_sum += arg._mean_log_loss
                self.kl_loss_sum += arg._kl_loss

        # Build this layer's sample model and mean model
        self.built_obj = self._build(self.built_args, data, batch_shape)
        self.mean_obj = self._build_mean(self.mean_args, data, batch_shape)


    def _parameter_list(self):
        """Get a list of parameters in this layer or its arguments."""
        params = []
        for arg in self.args:
            if isinstance(self.args[arg], BaseLayer):
                params += self.args[arg]._parameter_list()
            elif isinstance(self.args[arg], BaseParameter):
                params += [self.args[arg]]
        return params


    def _input_list(self):
        """Get a list of Input layers in this layer or its arguments."""
        inputs = []
        for arg in self.args:
            if self.args[arg].__class__.__name__ == 'Input':
                inputs += [self.args[arg]]
            elif isinstance(self.args[arg], BaseLayer):
                inputs += self.args[arg]._input_list()
        return inputs


    def __str__(self, prepend=''):
        """String representation of a layer (and all its args)."""

        # Settings
        max_short = 40 #max length of a short representation
        ind = '  ' #indentation to use

        # Make string representation of this layer and its args
        self_str = self.__class__.__name__
        arg_strs = dict()
        for arg in self._default_args:
            if isinstance(self.args[arg], (int, float)):
                arg_strs[arg] = str(self.args[arg])
            elif isinstance(self.args[arg], (np.ndarray)):
                arg_strs[arg] = 'np.ndarray shape='+str(self.args[arg].shape)
            elif isinstance(self.args[arg], (tf.Tensor, tf.Variable)):
                arg_strs[arg] = self.args[arg].__str__()
            elif isinstance(self.args[arg], (BaseParameter, BaseLayer)):
                tstr = self.args[arg].__str__(prepend=prepend+2*ind)
                if len(tstr) < max_short:
                    arg_strs[arg] = tstr
                else:
                    arg_strs[arg] = '\n'+tstr
            else:
                arg_strs[arg] = '???'

        # Try a short representation
        short_args = [a+' = '+arg_strs[a] for a in self._default_args]
        short_str = self_str+'('+', '.join(short_args)+')'
        if len(short_str) < max_short:
            return short_str

        # Use a longer representation if the shorter one failed
        return '\n'.join([prepend+self_str] +
                         [prepend+ind+a+' = '+arg_strs[a] 
                          for a in self._default_args])



class BaseDistribution(BaseLayer):
    r"""Abstract base class for ProbFlow |Distributions|

    This is an abstract base class for |Distributions|.  Distributions are
    objects which take |Tensors|, |Parameters|, or |Layers| as input, and
    output a probability distribution (unlike |Layers|, which output a 
    tensor).  The output probability distribution is the predicted observation
    distribution for the dependent variable given the independent variables.
    A |Distribution| should be the *final* layer in a model, and is used to 
    predict the dependent variable values.

    An inheriting class *must* define the following attributes and methods:

    * ``_default_args``
    * ``_post_param_bounds``
    * ``_post_param_init``    
    * ``_build(self, args, data, batch_shape)``

    The ``_default_args`` attribute should be a dict with keys containing
    the distribution's parameter names, and values containing the default
    value for each corresponding parameter.  To denote a required argument
    (when no default value makes sense, for example the rate parameter of 
    a Poisson distribution), set the value to the :obj:`.REQUIRED` object.

    The ``_post_param_bounds`` attribute should be a dict with keys
    corresponding to the distribution's parameter names, and values containing
    the corresponding bounds as tuples, where the first element of the tuple
    is the lower bound of that parameter, and the second element of the tuple
    is the upper bound of that parameter.  Use |None| when there is no
    bound on a given end.

    The ``_post_param_init`` should be a dict with keys containing the 
    distribution's parameters' names, and each corresponding value should
    contain an |Initializer| with which to initialize that parameter.

    Finally, the ``_build`` method should take input argument |Tensors| and
    return a |tfp.distribution| which has the parameters set to those 
    args.

    The :class:`.BaseDistribution` class also contains methods for fitting
    the model (the |Distribution| and all |Layers| and |Parameters| on which
    it depends), viewing the posteriors and priors of |Parameters| in the
    model, making point predictions on new data, computing predictive
    distributions on new data, computing confidence intervals, and more.
    These features are common to all |Distributions|, and so are implemented
    once in this class.

    
    Methods
    -------

    * :meth:`.fit`
    * :meth:`.predict`
    * :meth:`.metrics`
    * :meth:`.predictive_distribution`
    * :meth:`.plot_predictive_distribution`
    * :meth:`.posterior_mean`
    * :meth:`.posterior_sample`
    * :meth:`.posterior_plot`
    * :meth:`.prior_sample`
    * :meth:`.prior_plot`
    * :meth:`.posterior_plot_over_training`
    * :meth:`.posterior_plot_args_over_training`
    * :meth:`.prob`
    * :meth:`.prob_by`
    * :meth:`.log_prob`
    * :meth:`.log_prob_by`
    * :meth:`.cdf`
    * :meth:`.cdf_by`


    Examples
    --------

    The Normal distribution has two parameters: :math:`\mu` and 
    :math:`\sigma`.  Reasonable default values are :math:`\mu=0` and 
    :math:`\sigma=1`.  So, the ``_default_args`` attribute should be::

        _default_args = {
            'mu': 0.0,
            'sigma': 1.0
        }

    While the :math:`\mu` parameter is unbounded, the :math:`\sigma` parameter
    cannot be negative.  Therefore, the ``_post_param_bounds`` attribute 
    should be::

        _post_param_bounds = {
            'loc': (None, None),
            'scale': (0, None)
        }

    A good initialization scheme for the :math:`\mu` parameter is to choose 
    values from a normal distribution, and for the :math:`\sigma` parameter
    we want to initialize with positive values near 1.  So, the 
    ``_post_param_init`` attribute should be::

        _post_param_init = {
            'loc': tf.initializers.truncated_normal(mean=0.0, stddev=1.0),
            'scale': tf.initializers.random_uniform(minval=-0.7, maxval=0.4)
        }

    Finally, the ``_build`` method just needs to construct a
    |tfp.distribution| from the distribution's args::

        def _build(self, args, _data, _batch_shape):
            return tfd.Normal(loc=args['loc'], scale=args['scale'])

    Put together, a class to represent a Normal distribution which inherits
    from the :class:`.BaseDistribution` class should look like::

        class Normal(BaseDistribution):

            _default_args = {
                'mu': 0.0,
                'sigma': 1.0
            }

            _post_param_bounds = {
                'loc': (None, None),
                'scale': (0, None)
            }

            _post_param_init = {
                'loc': tf.initializers.truncated_normal(mean=0.0, stddev=1.0),
                'scale': tf.initializers.random_uniform(minval=-0.7, maxval=0.4)
            }

            def _build(self, args, _data, _batch_shape):
                return tfd.Normal(loc=args['loc'], scale=args['scale'])

    As a second example, we'll build a Poisson distribution.

    Unlike the Normal distribution, the Poisson distribution has one parameter
    (a rate parameter :math:`\lambda`), and that parameter has no obvious 
    default value, so we should make that parameter required::

        _default_args = {
            'lambda': REQUIRED
        }

    Like the Normal distribution's :math:`\sigma` parameter, the rate
    parameter :math:`\lambda` cannot be negative::

        _post_param_bounds = {
            'lambda': (0, None)
        }

    The default posterior parameter initializer is only used when the 
    |Distribution| is used as a variational posterior distribution.  The 
    Poisson distribution isn't often used as a variational posterior, but 
    we can define a default initializer anyway::

        _post_param_init = {
            'lambda': tf.initializers.random_uniform(minval=0.0, maxval=3.0),
        }

    And again, the ``_build`` method only has to return a |tfp.distribution|
    object with the args as parameters::

        def _build(self, args, _data, _batch_shape):
            return tfd.Poisson(args['lambda'])

    All together, this should look like::

        class Poisson(BaseDistribution):

            _default_args = {
                'lambda': REQUIRED
            }

            _post_param_bounds = {
                'lambda': (0, None)
            }

            _post_param_init = {
                'lambda': tf.initializers.random_uniform(minval=0.0, maxval=3.0),
            }

            def _build(self, args, _data, _batch_shape):
                return tfd.Poisson(args['lambda'])

    Note that the actual :class:`.Normal` and :class:`.Poisson` distributions
    inherit :class:`.ContinuousDistribution` and
    :class:`.DiscreteDistribution`, respectively, not 
    :class:`.BaseDistribution` (though both :class:`.ContinuousDistribution`
    and :class:`.DiscreteDistribution` inherit from
    :class:`.BaseDistribution`).

    For more examples, see the implementations of |Distribution| classes
    such as :class:`.Normal`, :class:`.Cauchy`, :class:`.Poisson`, and
    :class:`.Bernoulli`.

    """


    # Distribution parameters and their default values
    @property
    @abstractmethod
    def _default_args(self):
        pass


    # Posterior distribution parameter bounds (lower, upper)
    @property
    @abstractmethod
    def _post_param_bounds(self):
        pass


    # Posterior parameter initializers
    @property
    @abstractmethod
    def _post_param_init(self):
        pass


    def _log_loss(self, vals):
        """Compute the log loss ."""
        return self.built_obj.log_prob(vals)


    def _mean_log_loss(self, vals):
        """Compute the log loss ."""
        return self.mean_obj.log_prob(vals)


    def fit(self, x_in, y_in, data=None,
            dtype=tf.float32,
            batch_size=128,
            epochs=100,
            optimizer=tf.train.AdamOptimizer,
            optimizer_kwargs=dict(),
            learning_rate=0.01,
            metrics=[],
            verbose=True,
            validation_split=0.0,
            validation_shuffle=True,
            shuffle=True,
            record=None,
            record_freq='batch'):
        """Fit a model using stochastic variational inference.

        This function takes a matrix of independent variable values(``x_in``) 
        and a matrix of corresponding dependent variable values (``y_in``)
        and fits this |Model| to that data using variational inference.
        Alternatively, you can pass in a |DataFrame| with the ``data`` arg,
        and specify the variables in that DataFrame to use by passing ``x_in``
        and ``y_in`` as strings or ints or lists of strings or ints
        corresponding to the columns in ``data`` to use.

        For more information, see the sections in the user guide on
        :doc:`Bayesian modeling </inference>` and the
        :doc:`mathematical details </math>` behind variational inference.

        You must :meth:`.fit` a model to some data before calling any of the
        model criticism methods.


        Parameters
        ----------
        x_in : |DataFrame| or |ndarray| or int or str or list of str or int
            Independent variable values of the dataset to fit (aka the 
            "features").  If ``data`` was passed as a |DataFrame|, ``x`` can
            be an int or string or list of ints or strings specifying the
            columns of that |DataFrame| to use as independent variables.
        y_in : |DataFrame| or |Series| or |ndarray| or int or str or list of str or int
            Dependent variable values of the dataset to fit (aka the 
            "reponse"). If ``data`` was passed as a |DataFrame|, ``y`` can be
            an int or string or list of ints or strings specifying the columns
            of that |DataFrame| to use as dependent variables.
        data : |None| or |DataFrame|
            Data for the fit.  If ``data`` is |None|, :meth:`.fit` assumes 
            ``x`` and ``y`` are each an |ndarray| or |DataFrames|.  If 
            ``data`` is a |DataFrame|, :meth:`.fit` assumes ``x`` and ``y``
            are strings or lists of strings containing the columns from
            ``data`` to use.
            Default = |None|
        dtype : |DType|
            Cast the input data to this type, and use this type for parameters.
            Default = ``tf.float32``
        batch_size : int or None
            Number of samples per training batch.  Use None to use all samples
            per batch.
            Default = 128
        epochs : int
            Number of epochs to train for (1 epoch is one full cycle through
            all the training data).
            Default = 100
        optimizer : |Optimizer| class
            Optimizer to use.  Default is the
            `Adam <https://www.tensorflow.org/api_docs/python/tf/train/AdamOptimizer>`_
            optimizer.
        optimizer_kwargs : dict
            Keyword arguments to pass to the ``optimizer``.  Default is no
            keyword arguments.
        learning_rate : float
            Learning rate to use for the ``optimizer``.
            Default = 0.01
        metrics : str or list of str
            Metrics to evaluate each epoch.  To evaluate multiple metrics, 
            pass a list of strings, where each string is a different metric.
            Available metrics:

            * 'acc': accuracy
            * 'accuracy': accuracy
            * 'mse': mean squared error
            * 'sse': sum of squared errors
            * 'mae': mean absolute error

            Default = empty list
        verbose : bool
            Whether to print progress and metrics throughout training.
            Default = True
        validation_split : float between 0 and 1
            Proportion of the data to use as validation data.
            If 0, won't evaluate metrics on the validation data.
            Default = 0
        validation_shuffle : bool
            Whether to shuffle which data is used for validation.  If False,
            the last ``validation_split`` proportion of the input data is used
            for validation.
            Default = True
        shuffle : bool
            Whether to shuffle the training data before each training epoch.
            Default = True
        record : None or str or list of str
            Parameters to record over the course of training.  If ``record``
            is |None|, no parameter recording occurrs.  If ``record`` is 
            ``'all'``, all parameters are recorded.  If ``record`` is a string
            containing the name of a |Parameter|, that parameter's variational
            posterior parameters are recorded.  If ``record`` is a list, each
            element of the list should be a string with the name of a
            |Parameter| to record.
            Default = |None|
        record_freq : str {'batch' or 'epoch'}
            Recording frequency.  If ``record_freq='batch'``, 
            variational posterior parameters will be recorded once per batch.
            If ``record_freq='epoch'``, variational posterior parameters
            will only be recorded once per epoch (which saves memory if your
            model has many parameters). 
            Default = ``'batch'``

        Examples
        --------

        After constructing a simple model::

            from probflow import Parameter, Normal
            x1 = Input(0)
            x2 = Input(1)
            w1 = Parameter()
            w2 = Parameter()
            bias = Parameter(name='bias')
            predictions = x1*w1 + x2*w2 + bias
            model = Normal(predictions, 1.0)

        that model can be fit to some data. 
        This data can be numpy |ndarrays| ::

            import numpy as np
            x = np.random.randn(100, 2)
            w = np.array([0.5, -0.3])
            y = w*x - 0.7 + np.random.randn(100, 1)

            model.fit(x, y)

        The data can also be pandas |DataFrames| or |Series| ::

            import pandas as pd
            df_x = pd.DataFrame(x)
            df_y = pd.Series(y.ravel())

            model.fit(df_x, df_y)

        Or, you can pass in a single |DataFrame| using the ``data`` keyword
        argument, and specify which columns to use as the dependent and
        independent variables by passing strings or lists of strings 
        corresponding to the columns to use in ``x`` and ``y`` ::

            df = pd.DataFrame(x, columns=['feature1', 'feature2'])
            df['target'] = y

            model.fit(x=['feature1', 'feature2'],
                      y='target',
                      data=df)

        The batch size, number of training epochs, and learning rate of the
        optimizer can be set using the ``batch_size``, ``epochs``, and 
        ``learning_rate`` parameters::

            model.fit(x, y, 
                      batch_size=1028,
                      epochs=1000,
                      learning_rate=0.001)

        To track various metrics over training, use the ``metrics`` and 
        ``validation_split`` arguments::

            model.fit(x, y, 
                      metrics='mse',
                      validation_split=0.2)

        To record parameters over the course of training, use the
        ``record`` and ``record_freq`` arguments::

            model.fit(x, y,
                      record='bias',
                      record_freq='epoch')

        After fitting the model, you can call criticism methods such as
        :meth:`.predictive_distribution`, :meth:`.predict`, 
        and :meth:`.posterior_plot`.
        """

        def make_placeholders(x, y, dtype):
            """Create x, y, and batch_shape placeholders"""

            # Store pointer to training data
            self._train = dict()
            self._train['x'] = x
            self._train['y'] = y

            # Data placeholders
            x_shape = list(x_train.shape)
            y_shape = list(y_train.shape)
            x_shape[0] = None
            y_shape[0] = None
            x_data = tf.placeholder(dtype, x_shape)
            y_data = tf.placeholder(dtype, y_shape)

            # Batch shape
            batch_size_ph = tf.placeholder(tf.int32, [1])

            # Store placeholders
            self._ph = dict()
            self._ph['batch_size'] = batch_size_ph
            self._ph['x'] = x_data
            self._ph['y'] = y_data

            return x_data, y_data, batch_size_ph


        def assign_input_info(cols, x_data):
            """Assigns integer values + nunique to Input objects"""

            def str2int(t_str, col_list):
                int_col = None
                for ix, col in enumerate(col_list):
                    if col == t_str:
                        int_col = ix
                if int_col is None:
                    raise RuntimeError(t_str+' not in x')
                return int_col

            inputs = self._input_list()
            for tin in inputs:
                t_col = tin.kwargs['cols']
                if isinstance(t_col, int):
                    tin._int_cols = t_col
                    tin._nunique = len(np.unique(x_data[:, t_col]))
                elif isinstance(t_col, str):
                    t_int = str2int(t_col, cols)
                    tin._int_cols = t_int
                    tin._nunique = len(np.unique(x_data[:, t_int]))
                elif isinstance(t_col, list):
                    int_cols = len(t_col)*[None]
                    for ix, col in enumerate(t_col):
                        if isinstance(col, str):
                            int_cols[ix] = str2int(col, cols)
                        elif isinstance(col, int):
                            int_cols[ix] = col
                        else:
                            raise RuntimeError('Input cols must be int, ' +
                                               'str, or list of either.')
                    tin._int_cols = int_cols


        def init_records(to_record, record_freq, epochs, n_batch):
            """Initialize dicts and arrays for recording posterior params"""
            if record_freq == 'batch':
                Nrecords = int(epochs*n_batch)
            else:
                Nrecords = int(epochs)
            records = dict()
            records['x_epochs'] = np.linspace(1, epochs, Nrecords)
            for record in to_record:
                if record not in [p.name for p in self._parameters]:
                    raise ValueError(record+' is not a parameter')
            for param in self._parameters:
                if param.name in to_record:
                    records[param.name] = dict()
                    t_shape = [Nrecords] + param.shape
                    for post_arg in param._params:
                        records[param.name][post_arg] = \
                            np.full(t_shape, np.nan)
            return records

        def save_records(ix):
            """Save posterior parameter values"""
            for param in self._parameters:
                if param.name in self._records:
                    for post_arg in param._params:
                        self._records[param.name][post_arg][ix,...] = \
                            self._session.run(param._params[post_arg])


        # Check input types
        if not isinstance(dtype, tf.DType):
            raise TypeError('dtype must be a TensorFlow DType')
        if not isinstance(batch_size, int):
            raise TypeError('batch_size must be an int')
        if batch_size < 1:
            raise TypeError('batch_size must be greater than 0')
        if not isinstance(epochs, int):
            raise TypeError('epochs must be an int')
        if epochs < 0:
            raise TypeError('epochs must be non-negative')
        #if not isinstance(optimizer, tf.train.Optimizer): #TODO uh this fails
        if not callable(optimizer):
            raise TypeError('optimizer must be a TensorFlow optimizer')
        if not isinstance(optimizer_kwargs, dict):
            raise TypeError('optimizer_kwargs must be a dict of keyword '
                            'arguments to pass to the optimizer')
        if not isinstance(learning_rate, float):
            raise TypeError('learning_rate must be a float')
        if learning_rate < 0:
            raise TypeError('learning_rate must be non-negative')
        if not isinstance(verbose, bool):
            raise TypeError('verbose must be True or False')
        if not isinstance(validation_split, float):
            raise TypeError('validation_split must be a float')
        if validation_split < 0 or validation_split > 1:
            raise TypeError('validation_split must be between 0 and 1')
        if not isinstance(validation_shuffle, bool):
            raise TypeError('validation_shuffle must be True or False')
        if not isinstance(shuffle, bool):
            raise TypeError('shuffle must be True or False')
        if record is not None and not isinstance(record, (str, list)):
            raise TypeError('record must be None, a string, or a list')
        if isinstance(record, list):
            if not all([isinstance(e, str) for e in record]):
                raise TypeError('record must be a list of strings')
        if not isinstance(record_freq, str):
            raise TypeError('record_freq must be a string')
        if record_freq not in ['batch', 'epoch']:
            raise ValueError('record_freq must be \'batch\' or \'epoch\'')

        # Process the input data
        x, y = process_xy_data(self, x_in, y_in, data)

        # Split data into training and validation data
        N, x_train, y_train, x_val, y_val = \
            test_train_split(x, y, validation_split, validation_shuffle)

        # Create placeholders for input data
        x_data, y_data, batch_size_ph = \
            make_placeholders(x_train, y_train, dtype)

        # Initialize the shuffling of training data
        shuff_ids = initialize_shuffles(N, epochs, shuffle)

        # Assign columns to Input objects
        if isinstance(x_in, pd.DataFrame):
            assign_input_info(x_in.columns.tolist(), x)
        elif isinstance(x_in, pd.Series):
            assign_input_info([x_in.name], x)
        else: #x_in is list of str or int
            assign_input_info(x_in, x)

        # Recursively build this model and its args
        self._build_recursively(x_data, batch_size_ph)

        # Set up TensorFlow graph for per-sample losses
        self.log_loss = (self.samp_loss_sum +  #size (batch_size,)
                         self._log_loss(y_data))
        self.mean_log_loss = (self.mean_loss_sum + #size (batch_size,)
                              self._mean_log_loss(y_data))
        self.kl_loss = tf.cast(self.kl_loss_sum + self._kl_loss(), dtype)

        # ELBO loss function
        log_likelihood = tf.reduce_mean(self.built_obj.log_prob(y_data))
        kl_loss = tf.reduce_sum(self.kl_loss) / N
        elbo_loss = kl_loss - log_likelihood

        # Optimizer
        with tf.name_scope('train'):
            optimizer_obj = optimizer(learning_rate=learning_rate,
                                      **optimizer_kwargs)
            train_op = optimizer_obj.minimize(elbo_loss)

        # Store a list of all parameters in the model
        self._parameters = self._parameter_list()

        # Ensure this model contains parameters
        if len(self._parameters) == 0:
            raise RuntimeError('model contains no parameters, cannot fit it!')

        # Create the TensorFlow session and assign it to each parameter
        self._session = tf.Session()
        for param in self._parameters:
            param._session = self._session

        # Initializers
        init_op = tf.group(tf.global_variables_initializer(),
                           tf.local_variables_initializer())
        self._session.run(init_op)

        # Set up arrays for recording
        n_batch = int(np.ceil(N/batch_size)) #number of batches per epoch
        if isinstance(record, str):
            if record == 'all':
                record = [p.name for p in self._parameters]
            else:
                record = [record] #make list if not
        if record is not None:
            self._records = init_records(record, record_freq, epochs, n_batch)

        # Fit the model
        self.is_fit = True
        print_batches = int(np.ceil(n_batch/10)) #info each print_batches batch
        for epoch in range(epochs):

            # Print progress
            if verbose:
                print('Epoch %d / %d' % (epoch, epochs))

            # Train on each batch in this epoch
            for batch in range(n_batch):
                b_x, b_y, b_n = generate_batch(x_train, y_train, epoch,
                                               batch, batch_size, shuff_ids)
                self._session.run(train_op,
                                  feed_dict={x_data: b_x,
                                             y_data: b_y,
                                             batch_size_ph: b_n})

                # Record variational posteriors each batch
                if record is not None and record_freq == 'batch':
                    save_records(epoch*n_batch + batch)

                # Print progress
                if verbose and batch % print_batches == 0:
                    print("  Batch %d / %d (%0.1f%%)\r" %
                          (batch+1, n_batch, 100.0*batch/n_batch), end='')

            # Record variational posteriors each epoch
            if record is not None and record_freq == 'epoch':
                save_records(epoch)

            # Evaluate metrics
            if metrics:
                md = self.metrics(x_val, y_val, metrics)

            # Print metrics
            if verbose:
                if metrics:
                    print('  '+(4*' ').join([m+': '+str(md[m]) for m in md]))
                print(60*' '+"\r", end='')

        # Finished!
        if verbose:
            print('Done!')


    def _ensure_is_fit(self):
        """Raises a RuntimeError if model has not yet been fit."""
        if not self.is_fit:
            raise RuntimeError('model must first be fit')


    def predictive_distribution(self, x=None, data=None, num_samples=1000):
        """Draw samples from the model given x.

        TODO: Docs...

        .. admonition:: Model must be fit first!

            Before calling :meth:`.predictive_distribution` on a |Model|, you
            must first :meth:`.fit` it to some data.

        Parameters
        ----------
        x : |ndarray| or |DataFrame| or int or str or list of str or int
            Independent variable values of the dataset to evaluate (aka the 
            "features").  If ``data`` was passed as a |DataFrame|, ``x`` can
            be an int or string or list of ints or strings specifying the 
            columns of that |DataFrame| to use as independent variables. If
            |None|,  will use the data the model was trained on (the default).
        data : |None| or |DataFrame|
            Data to evaluate.  If ``data`` is |None|, it is assumed that
            ``x`` and ``y`` are |ndarray| or |DataFrame| or |Series|.  
            If ``data`` is a |DataFrame|, ``x`` and ``y`` are treated as
            strings or lists of strings containing the columns from
            ``data`` to use as in- and de-pendent variables.
        num_samples : int
            Number of samples to draw from the model given ``x``.

        Returns
        -------
        |ndarray|
            Samples from the predictive distribution.  Size
            (num_samples,x.shape[0],y.shape[0],...,y.shape[-1])        
        """        

        # Check model has been fit
        self._ensure_is_fit()

        # Process input data
        x = process_data(self, x, data)

        # Check other inputs
        if not isinstance(num_samples, int):
            raise TypeError('num_samples must be an int')
        if num_samples < 1:
            raise ValueError('num_samples must be greater than 0')

        # Draw samples from the predictive distribution
        return self._session.run(
            self.built_obj.sample(num_samples),
            feed_dict={self._ph['x']: x,
                       self._ph['batch_size']: [x.shape[0]]})


    def predictive_distribution_plot(self, x=None, 
                                     data=None, 
                                     num_samples=1000,
                                     style='fill',
                                     cols=1,
                                     bins=20,
                                     ci=0.0,
                                     bw=0.075,
                                     color=None,
                                     alpha=0.4,
                                     individually=False):
        """Plot samples from the model given x.

        TODO: Docs...

        .. admonition:: Model must be fit first!

            Before calling :meth:`.plot_predictive_distribution` on a |Model|,
            you must first :meth:`.fit` it to some data.

        TODO: another admonition about how this only works with
        a continuous model whose y-variable is 1D.
        TODO: or, could have separate ones for ContinuousModel and Discrete...

        Parameters
        ----------
        x : |ndarray| or |DataFrame| or int or str or list of str or int
            Independent variable values of the dataset to evaluate (aka the 
            "features").  If ``data`` was passed as a |DataFrame|, ``x`` can
            be an int or string or list of ints or strings specifying the 
            columns of that |DataFrame| to use as independent variables. If
            |None|,  will use the data the model was trained on (the default).
        data : |None| or |DataFrame|
            Data to evaluate.  If ``data`` is |None|, it is assumed that
            ``x`` and ``y`` are |ndarray| or |DataFrame| or |Series|.  
            If ``data`` is a |DataFrame|, ``x`` and ``y`` are treated as
            strings or lists of strings containing the columns from
            ``data`` to use as in- and de-pendent variables.
        num_samples : int
            Number of samples to draw from the model given ``x``.
        style : str
            Which style of plot to show.  Available types are:

            * ``'fill'`` - filled density plot (the default)
            * ``'line'`` - line density plot
            * ``'hist'`` - histogram

        cols : int
            Divide the subplots into a grid with this many columns (if 
            ``individually=True``.
        bins : int or list or |ndarray|
            Number of bins to use for the posterior density histogram (if 
            ``style='hist'``), or a list or vector of bin edges.
        ci : float between 0 and 1
            Confidence interval to plot.  Default = 0.0 (i.e., not plotted)
        bw : float
            Bandwidth of the kernel density estimate (if using ``style='line'``
            or ``style='fill'``).  Default is 0.075
        color : matplotlib color code or list of them
            Color(s) to use to plot the distribution.
            See https://matplotlib.org/tutorials/colors/colors.html
            Default = use the default matplotlib color cycle
        alpha : float between 0 and 1
            Transparency of fill/histogram of the density
        individually : bool
            If ``True``, plot one subplot per datapoint in ``x``, otherwise
            plot all the predictive distributions on the same plot.
        """

        # Sample from the predictive distribution
        pred_dist = self.predictive_distribution(x=x, data=data, 
                                                 num_samples=num_samples)

        # Squeeze singleton dimension (assumes dep var is scalar)
        pred_dist = pred_dist[...,0]
        # TODO: ensure y is scalar

        # Plot the predictive distributions
        N = pred_dist.shape[1]
        if individually:
            rows = np.ceil(N/cols)
            for i in range(N):
                plt.subplot(rows, cols, i+1)
                plot_dist(pred_dist[:,i], xlabel='Datapoint '+str(i), 
                          style=style, bins=bins, ci=ci, bw=bw, alpha=alpha, 
                          color=color)
        else:
            plot_dist(pred_dist, xlabel='Dependent Variable', style=style, 
                      bins=bins, ci=ci, bw=bw, alpha=alpha, color=color)


    def predict(self, x=None, data=None):
        """Predict dependent variable using the model

        TODO: option for whether to use the mean model, or mean of the 
        predictive distribution

        .. admonition:: Model must be fit first!

            Before calling :meth:`.predict` on a |Model|, you must first
            :meth:`.fit` it to some data.

        Parameters
        ----------
        x : |ndarray| or |DataFrame| or int or str or list of str or int
            Independent variable values of the dataset to evaluate (aka the 
            "features").  If ``data`` was passed as a |DataFrame|, ``x`` can
            be an int or string or list of ints or strings specifying the 
            columns of that |DataFrame| to use as independent variables. If
            |None|,  will use the data the model was trained on (the default).
        data : |None| or |DataFrame|
            Data to evaluate.  If ``data`` is |None|, it is assumed that
            ``x`` and ``y`` are |ndarray| or |DataFrame| or |Series|.  
            If ``data`` is a |DataFrame|, ``x`` and ``y`` are treated as
            strings or lists of strings containing the columns from
            ``data`` to use as in- and de-pendent variables.

        Returns
        -------
        |ndarray|
            Predicted y-value for each sample in ``x``.  Will be of
            size ``(N, D_out)``, where N is the number of samples (equal
            to ``x.shape[0]``) and D_out is the number of output
            dimensions (equal to ``y.shape[1:]``).

        Examples
        --------
        TODO: Docs...

        """

        # Check model has been fit
        self._ensure_is_fit()

        # Process input data
        x = process_data(self, x, data)

        # Predict using the mean model
        return self._session.run(
            self.mean_obj.mean(), 
            feed_dict={self._ph['x']: x,
                       self._ph['batch_size']: [x.shape[0]]})


    def metrics(self, metric_list=[], x=None, y=None, data=None):
        """Compute metrics of model performance.

        TODO: docs

        TODO: methods which just call this w/ a specific metric? for shorthand

        .. admonition:: Model must be fit first!

            Before calling :meth:`.metrics` on a |Model|, you must first
            :meth:`.fit` it to some data.

        Parameters
        ----------
        metric_list : str or list of str
            Metrics to evaluate each epoch.  To evaluate multiple metrics, 
            pass a list of strings, where each string is a different metric.
            Available metrics:

            * 'acc': accuracy
            * 'accuracy': accuracy
            * 'mse': mean squared error
            * 'sse': sum of squared errors
            * 'mae': mean absolute error

            Default = empty list
        x : |ndarray| or |DataFrame| or int or str or list of str or int
            Independent variable values of the dataset to evaluate (aka the 
            "features").  If ``data`` was passed as a |DataFrame|, ``x`` can
            be an int or string or list of ints or strings specifying the 
            columns of that |DataFrame| to use as independent variables. If
            |None|,  will use the data the model was trained on (the default).
        y : |ndarray| or |DataFrame| or |Series| or int or str or list of str or int
            Dependent variable values of the dataset to evaluate (aka the 
            "target"). If ``data`` was passed as a |DataFrame|, ``y`` can be
            an int or string or list of ints or strings specifying the columns
            of that |DataFrame| to use as dependent variables. If |None|, 
            will use the data the model was trained on (the default).
        data : |None| or |DataFrame|
            Data to evaluate.  If ``data`` is |None|, it is assumed that
            ``x`` and ``y`` are |ndarray| or |DataFrame| or |Series|.  
            If ``data`` is a |DataFrame|, ``x`` and ``y`` are treated as
            strings or lists of strings containing the columns from
            ``data`` to use as in- and de-pendent variables.
        """

        # Check types
        if not isinstance(metric_list, (str, list)):
            raise ValueError('metric_list must be a string or list of strings')
        if isinstance(metric_list, list):
            if not all([isinstance(e, str) for e in metric_list]):
                raise ValueError('metric_list must be a list of strings')

        # Make list if metric_list is not
        if isinstance(metric_list, str):
            metric_list = [metric_list]

        # Process input data
        x, y = process_xy_data(self, x, y, data)

        # Make predictions
        y_pred = self.predict(x)

        # Dict to store metrics
        metrics = dict()

        # Compute accuracy
        if 'acc' in metric_list or 'accuracy' in metric_list:
            metrics['accuracy'] = np.mean(y == y_pred)

        # Compute mean squared error
        if 'mse' in metric_list:
            metrics['mse'] = np.mean(np.square(y-y_pred))

        # Compute sum of squared errors
        if 'sse' in metric_list:
            metrics['sse'] = np.sum(np.square(y-y_pred))

        # Compute mean squared error
        if 'mae' in metric_list:
            metrics['mae'] = np.mean(y-y_pred)

        # TODO: r^2, cross-entropy, etc

        return metrics


    def posterior_mean(self, params=None):
        """Get the mean of the posterior distribution(s).

        TODO: Docs... params is a list of strings of params to plot

        .. admonition:: Model must be fit first!

            Before calling :meth:`.posterior_mean` on a |Model|, you must first
            :meth:`.fit` it to some data.

        Parameters
        ----------
        params : list
            List of parameter names to sample.  Each element should be a str.

        Returns
        -------
        dict
            Means of the parameter posterior distributions.  A dictionary
            where the keys contain the parameter names and the values contain
            |ndarray|s with the posterior means.  The |ndarray|s are the same
            size as each parameter.
        """

        # Check model has been fit
        self._ensure_is_fit()

        # Check parameter list
        param_dict = self._validate_params(params)

        # Get the posterior means
        posterior_means = dict()
        for name, param in param_dict.items():
            posterior_means[name] = param.posterior_mean()

        return posterior_means


    def posterior_sample(self, params=None, num_samples=1000):
        """Draw samples from parameter posteriors.

        TODO: Docs... params is a list of strings of params to plot

        .. admonition:: Model must be fit first!

            Before calling :meth:`.posterior_sample` on a |Model|, you must 
            first :meth:`.fit` it to some data.

        Parameters
        ----------
        params : list
            List of parameter names to sample.  Each element should be a str.
        num_samples : int
            Number of samples to take from each posterior distribution.
            Default = 1000

        Returns
        -------
        dict
            Samples from the parameter posterior distributions.  A dictionary
            where the keys contain the parameter names and the values contain
            |ndarray|s with the posterior samples.  The |ndarray|s are of size
            (``num_samples``,param.shape).
        """

        # Check model has been fit
        self._ensure_is_fit()

        # Check parameter list
        param_dict = self._validate_params(params)

        # Check other inputs
        if not isinstance(num_samples, int):
            raise TypeError('num_samples must be an int')
        if num_samples < 1:
            raise ValueError('num_samples must be greater than 0')

        # Get the posterior distributions
        posteriors = dict()
        for name, param in param_dict.items():
            posteriors[name] = param.posterior_sample(num_samples=num_samples)

        return posteriors


    def posterior_plot(self,
                       params=None,
                       num_samples=1000,
                       style='fill',
                       cols=1,
                       bins=20,
                       ci=0.0,
                       bw=0.075,
                       color=None,
                       alpha=0.4):
        """Plot posterior distributions of the model's parameters.

        TODO: Docs... params is a list of strings of params to plot

        .. admonition:: Model must be fit first!

            Before calling :meth:`.posterior_plot` on a |Model|, you must
            first :meth:`.fit` it to some data.

        Parameters
        ----------
        params : str or list
            List of parameters to plot.  Default is to plot the posterior of
            all parameters in the model.
        num_samples : int
            Number of samples to take from each posterior distribution for
            estimating the density.  Default = 1000
        style : str
            Which style of plot to show.  Available types are:

            * ``'fill'`` - filled density plot (the default)
            * ``'line'`` - line density plot
            * ``'hist'`` - histogram

        cols : int
            Divide the subplots into a grid with this many columns.
        bins : int or list or |ndarray|
            Number of bins to use for the posterior density histogram (if 
            ``style='hist'``), or a list or vector of bin edges.
        ci : float between 0 and 1
            Confidence interval to plot.  Default = 0.0 (i.e., not plotted)
        bw : float
            Bandwidth of the kernel density estimate (if using ``style='line'``
            or ``style='fill'``).  Default is 0.075
        color : matplotlib color code or list of them
            Color(s) to use to plot the distribution.
            See https://matplotlib.org/tutorials/colors/colors.html
            Default = use the default matplotlib color cycle
        alpha : float between 0 and 1
            Transparency of fill/histogram of the density
        """

        # Check model has been fit
        self._ensure_is_fit()

        # Check parameter list
        param_dict = self._validate_params(params)

        # Check other inputs
        if not isinstance(num_samples, int):
            raise TypeError('num_samples must be an int')
        if num_samples < 1:
            raise ValueError('num_samples must be greater than 0')
        if type(cols) is not int:
            raise TypeError('cols must be an integer')
        if not isinstance(bins, (int, float, np.ndarray)):
            raise TypeError('bins must be an int or list or numpy vector')
        if type(ci) is not float or ci<0.0 or ci>1.0:
            raise TypeError('ci must be a float between 0 and 1')
        if type(alpha) is not float or alpha<0.0 or alpha>1.0:
            raise TypeError('alpha must be a float between 0 and 1')

        # Plot each parameter's posterior distributions in separate subplot
        rows = np.ceil(len(param_dict)/cols)
        for ix, param in enumerate(param_dict):
            plt.subplot(rows, cols, ix+1)
            param_dict[param].posterior_plot(num_samples=num_samples, 
                                             style=style, bins=bins, ci=ci,
                                             color=color)


    def posterior_plot_over_training(self, 
                                     params=None,
                                     cols=1,
                                     ci=[0.1, 0.5, 0.95],
                                     marker='-',
                                     alpha=0.3,
                                     color=None):
        """Plot the variational posteriors over the course of training.

        Plots confidence intervals of the variational posterior distributions
        across training epochs.

        TODO: more docs... 

        .. admonition:: Model must be fit first!

            Before calling :meth:`.posterior_plot_over_training` on a |Model|,
            you must first :meth:`.fit` it to some data.

        Parameters
        ----------
        params : |None| or str or list of str
            List of parameters to plot.  Default is to plot the posteriors of
            all parameters in the model over the course of training.
        cols : int
            Divide the subplots into a grid with this many columns.
        ci : list of float between 0 and 1
            Confidence intervals to plot.  Default = ``[0.1, 0.5, 0.95]``.
        marker : str or matplotlib linespec
            Line marker to use.
        alpha : float between 0 and 1
            Transparency of density polygons
        color : matplotlib color code or list of them
            Color(s) to use to plot the distribution.
            See https://matplotlib.org/tutorials/colors/colors.html
            Default = use the default matplotlib color cycle
        """

        # Check model has been fit
        self._ensure_is_fit()

        # Check parameter list
        param_dict = self._validate_params(params, rec=True)

        # Check other inputs
        if not isinstance(cols, int):
            raise TypeError('cols must be an integer')
        if cols < 1:
            raise ValueError('cols must be greater than 0')
        if not isinstance(ci, (float, list)):
            raise TypeError('ci must be a float or a list of floats')
        if isinstance(ci, list):
            for c in ci:
                if not isinstance(c, float):
                    raise TypeError('ci must be a float or a list of floats')

        # X values
        x_vals = self._records['x_epochs']
        x_res = len(x_vals)

        # Compute confidence interval percentiles
        ci = np.array(ci)
        ci_lb = 0.5 - ci/2.0
        ci_ub = 0.5 + ci/2.0

        # Plot confidence intervals over training
        ix = 0
        rows = np.ceil(len(param_dict)/cols)
        for name, param in param_dict.items():

            # Create a TFP distribution of the posterior across training
            t_post = param.posterior_fn(**self._records[name])
            t_post._build_recursively(None, None)
            t_post = t_post.built_obj

            # Compute the quantiles
            tfo = param.transform
            lb = np.empty([len(ci), x_res]+param.shape)
            ub = np.empty([len(ci), x_res]+param.shape)
            with tf.Session() as sess:
                for iy in range(len(ci)):
                    lb[iy,...] = sess.run(tfo(t_post.quantile(ci_lb[iy])))
                    ub[iy,...] = sess.run(tfo(t_post.quantile(ci_ub[iy])))

            # Plot the quantiles
            plt.subplot(rows, cols, ix+1)
            fill_between(x_vals, lb, ub, xlabel='Epoch', ylabel=name, 
                         alpha=alpha, color=color)
            ix += 1


    def posterior_plot_args_over_training(self, 
                                          params=None,
                                          cols=1,
                                          marker='-'):
        """Plot the variational posterior's parameters across training.

        TODO: more docs...

        .. admonition:: Model must be fit first!

            Before calling :meth:`.posterior_plot_args_over_training` on a 
            |Model|, you must first :meth:`.fit` it to some data.

        Parameters
        ----------
        params : |None| or str or list of str
            List of parameters to plot.  Default is to plot the posteriors of
            all parameters in the model over the course of training.
        cols : int
            Divide the subplots into a grid with this many columns.
        marker : str or matplotlib linespec
            Line marker to use.
        """

        # Check model has been fit
        self._ensure_is_fit()

        # Check parameter list
        param_dict = self._validate_params(params, rec=True)

        # Check other inputs
        if not isinstance(cols, int):
            raise TypeError('cols must be an integer')
        if cols < 1:
            raise ValueError('cols must be greater than 0')

        # Count how many posterior arguments there are
        n_args = 0
        for _, param in param_dict.items():
            n_args += len(param._params)

        # Plot each variational posterior's argument in separate subplot
        rows = np.ceil(n_args/cols)
        ix = 0
        x_vals = self._records['x_epochs']
        for name, param in param_dict.items():
            for arg in param._params:
                plt.subplot(rows, cols, ix+1)
                plot_line(x_vals, self._records[name][arg], fmt=marker,
                          xlabel='Epoch', ylabel=name+'\n'+arg)
                ix += 1


    def prior_sample(self, params=None, num_samples=10000):
        """Draw samples from parameter priors.

        TODO: Docs... params is a list of strings of params to plot

        .. admonition:: Model must be fit first!

            Before calling :meth:`.prior_sample` on a |Model|, you must first
            :meth:`.fit` it to some data.

        Parameters
        ----------
        params : list
            List of parameter names to sample.  Each element should be a str.
        num_samples : int
            Number of samples to take from each prior distribution.
            Default = 10000

        Returns
        -------
        dict
            Samples from the parameter prior distributions.  A dictionary
            where the keys contain the parameter names and the values contain
            |ndarray|s with the prior samples.  The |ndarray|s are of size
            (``num_samples``,param.shape).
        """

        # Check model has been fit
        self._ensure_is_fit()

        # Check parameter list
        param_dict = self._validate_params(params)

        # Check other inputs
        if not isinstance(num_samples, int):
            raise TypeError('num_samples must be an int')
        if num_samples < 1:
            raise ValueError('num_samples must be greater than 0')

        # Get the prior distribution samples
        priors = dict()
        for name, param in param_dict.items():
            priors[name] = param.prior_sample(num_samples=num_samples)

        return priors


    def prior_plot(self,
                   params=None,
                   num_samples=10000,
                   style='fill',
                   cols=1,
                   bins=20,
                   ci=0.0,
                   bw=0.075,
                   color=None,
                   alpha=0.4):
        """Plot prior distributions of the model's parameters.

        TODO: Docs... params is a list of strings of params to plot

        .. admonition:: Model must be fit first!

            Before calling :meth:`.prior_plot` on a |Model|, you must
            first :meth:`.fit` it to some data.

        Parameters
        ----------
        params : |None| or str or list of str
            List of parameters to plot.  Default is to plot the prior of
            all parameters in the model.
        num_samples : int
            Number of samples to take from each prior distribution.
            Default = 10000
        style : str
            Which style of plot to show.  Available types are:

            * ``'fill'`` - filled density plot (the default)
            * ``'line'`` - line density plot
            * ``'hist'`` - histogram

        cols : int
            Divide the subplots into a grid with this many columns.
        bins : int or list or |ndarray|
            Number of bins to use for the prior density histogram (if 
            ``style='hist'``), or a list or vector of bin edges.
        ci : float between 0 and 1
            Confidence interval to plot.  Default = 0.0 (i.e., not plotted)
        bw : float
            Bandwidth of the kernel density estimate (if using ``style='line'``
            or ``style='fill'``).  Default is 0.075
        color : matplotlib color code or list of them
            Color(s) to use to plot the distribution.
            See https://matplotlib.org/tutorials/colors/colors.html
            Default = use the default matplotlib color cycle
        alpha : float between 0 and 1
            Transparency of fill/histogram of the density
        """

        # Check model has been fit
        self._ensure_is_fit()

        # Check parameter list
        param_dict = self._validate_params(params)

        # Check other inputs
        if not isinstance(num_samples, int):
            raise TypeError('num_samples must be an int')
        if num_samples < 1:
            raise ValueError('num_samples must be greater than 0')
        if type(style) is not str or style not in ['fill', 'line', 'hist']:
            raise TypeError("style must be \'fill\', \'line\', or \'hist\'")
        if type(cols) is not int:
            raise TypeError('cols must be an integer')
        if not isinstance(bins, (int, float, np.ndarray)):
            raise TypeError('bins must be an int or list or numpy vector')
        if type(ci) is not float or ci<0.0 or ci>1.0:
            raise TypeError('ci must be a float between 0 and 1')
        if type(alpha) is not float or alpha<0.0 or alpha>1.0:
            raise TypeError('alpha must be a float between 0 and 1')

        # Plot each parameter's prior distribution in separate subplot
        rows = np.ceil(len(param_dict)/cols)
        for ix, param in enumerate(param_dict):
            plt.subplot(rows, cols, ix+1)
            param_dict[param].prior_plot(num_samples=num_samples, style=style, 
                                         bins=bins, ci=ci, color=color)

            
    def _validate_params(self, params, rec=False):
        """Check params list is valid."""

        # Check types
        if params is not None and not isinstance(params, (list, str)):
            raise TypeError('params must be None or a list of str')
        if type(params) is list:
            for param in params:
                if not isinstance(param, str):
                    raise TypeError('params must be None or a list of str')

        # Get all params if not specified
        if params is None:
            params = [p.name for p in self._parameters]

        # Make list if string was passed
        if isinstance(params, str):
            params = [params]

        # Check requested parameters are in the model
        for param in params:
            if param not in [p.name for p in self._parameters]:
                raise ValueError('Parameter \''+param+'\' not in this model')

        # Check requested parameters were recorded
        if rec:
            for param in params:
                if param not in self._records:
                    raise ValueError('Parameter \''+param+'\' was not ' +
                                     'recorded. To record, set the record ' +
                                     'argument when calling fit().')

        # Make dict of params to get
        param_dict = dict()
        for param in self._parameters:
            if param.name in params:
                param_dict[param.name] = param

        return param_dict


    def _int_x_by(self, x_by, x, y, data):
        """Convert x_by argument to plot_by functions to an integer"""
        if isinstance(x_by, list):
            if len(x_by) == 2:
                x_bys = list()
                x_bys.append(self._int_x_by(x_by[0], x, y, data))
                x_bys.append(self._int_x_by(x_by[1], x, y, data))
                return x_bys
            else:
                raise ValueError('x_by must be a 2-element list')
        elif isinstance(x_by, int):
            return x_by
        elif instantiated(x_by, str):
            if isinstance(x, pd.DataFrame):
                if x_by in x:
                    return x.columns.tolist().index(x_by)
                else:
                    raise KeyError(x_by+' is not a column in x')
                    # TODO: this'll throw an error when using training data tho...
            elif isinstance(data, pd.DataFrame):
                if isinstance(x, list):
                    if all(isinstance(e, str) for e in x):
                        return x.index(x_by)
                    else:
                        raise TypeError('x_by cannot be a str if all elements'
                                        ' of x are not str')
                elif isinstance(x, str):
                    if x == x_by:
                        return 0
                    else:
                        raise ValueError(x_by+' not in x')
                elif isinstance(x, int):
                    raise TypeError('x_by must be an int if x is an int')
            else:
                raise TypeError('x_by cannot be a string if neither x nor '
                                'data are pandas DataFrames')
        else:
            raise TypeError('x_by must be a str, int, or list of str or int')


    def log_prob(self, x=None, y=None, data=None, 
                 individually=True, dist=False, num_samples=1000):
        """Compute the log probability of `y` given `x` and the model.

        TODO: Docs...

        .. admonition:: Model must be fit first!

            Before calling :meth:`.log_prob` on a |Model|, you must first
            :meth:`.fit` it to some data.

        if individually is True, returns prob for each sample individually
            so return shape is (x.shape[0],?)
        if individually is False, returns product of each individual prob
            so return shape is (1,?)
        if dist is True, returns log probability posterior distribution
            (distribution of probs for lots of samples from the model)
            so return shape is (?,num_samples)
        if dist is False, returns log posterior prob assuming each parameter
            takes the mean value of its variational distribution
            so return shape iss (?,1)

        Parameters
        ----------
        x : |ndarray| or |DataFrame| or int or str or list of str or int
            Independent variable values of the dataset to evaluate (aka the 
            "features").  If ``data`` was passed as a |DataFrame|, ``x`` can
            be an int or string or list of ints or strings specifying the 
            columns of that |DataFrame| to use as independent variables. If
            |None|,  will use the data the model was trained on (the default).
        y : |ndarray| or |DataFrame| or |Series| or int or str or list of str or int
            Dependent variable values of the dataset to evaluate (aka the 
            "target"). If ``data`` was passed as a |DataFrame|, ``y`` can be
            an int or string or list of ints or strings specifying the columns
            of that |DataFrame| to use as dependent variables. If |None|, 
            will use the data the model was trained on (the default).
        data : |None| or |DataFrame|
            Data to evaluate.  If ``data`` is |None|, it is assumed that
            ``x`` and ``y`` are |ndarray| or |DataFrame| or |Series|.  
            If ``data`` is a |DataFrame|, ``x`` and ``y`` are treated as
            strings or lists of strings containing the columns from
            ``data`` to use as in- and de-pendent variables.

        """

        # Check model has been fit
        self._ensure_is_fit()

        # Process input data
        x, y = process_xy_data(self, x, y, data)

        # TODO: make dataset/iterator/feed_dict of x and y

        # Compute probability of y given x
        # TODO
        # if dist:
        #   #sample prob from self.mean_obj.prob()?
        # else:
        #   tf_prob = self.mean_obj.prob()
        # with tf.Session() as sess:
        #   prob = sess.run(tf_prob, feed_dict=???) #make the feed dict x and y

        # TODO: but will have to SAMPLE from model and compute prob multiple times?
        # then what - take average? or median.
        # that doesn't make sense...
        # somehow need to be able to take the mean of every variational parameter...
        # which is - sigh - intercepting like in edward.
        # the predict() method should use that too
        # maybe you should also have meanify(), and meanify_args()
        #   as the equivalents of build(), and build_args(), but using the
        #   mean of any distribution?


    def log_prob_by(self, x_by, x=None, y=None, data=None, 
                    bins=30, plot=True):
        """Plot the log probability of observations `y` given `x` and the model
        as a function of independent variable(s) `x_by`.

        TODO: docs...

        .. admonition:: Model must be fit first!

            Before calling :meth:`.log_prob_by` on a |Model|, you must first
            :meth:`.fit` it to some data.

        Parameters
        ----------
        x_by : int or string or 2-element list of int or string
            Which independent variable(s) to plot the log probability as a
            function of.  That is, which columns in ``x`` to plot by.
        x : |ndarray| or |DataFrame| or int or str or list of str or int
            Independent variable values of the dataset to evaluate (aka the 
            "features").  If ``data`` was passed as a |DataFrame|, ``x`` can
            be an int or string or list of ints or strings specifying the 
            columns of that |DataFrame| to use as independent variables. If
            |None|,  will use the data the model was trained on (the default).
        y : |ndarray| or |DataFrame| or |Series| or int or str or list of str or int
            Dependent variable values of the dataset to evaluate (aka the 
            "target"). If ``data`` was passed as a |DataFrame|, ``y`` can be
            an int or string or list of ints or strings specifying the columns
            of that |DataFrame| to use as dependent variables. If |None|, 
            will use the data the model was trained on (the default).
        data : |None| or |DataFrame|
            Data to evaluate.  If ``data`` is |None|, it is assumed that
            ``x`` and ``y`` are |ndarray| or |DataFrame| or |Series|.  
            If ``data`` is a |DataFrame|, ``x`` and ``y`` are treated as
            strings or lists of strings containing the columns from
            ``data`` to use as in- and de-pendent variables.

        """

        # Check model has been fit
        self._ensure_is_fit()

        # Convert x_by to list of int
        x_by = self._int_x_by(x_by, x, y, data)

        # Compute the log model posterior probability for each observation
        probs = self.log_prob(x, y)

        # Process input data
        x, y = process_xy_data(self, x, y, data)

        # Plot probability as a fn of x_by cols of x
        px, py = plot_by(x[:, x_by], probs, bins=bins, plot=plot)

        return px, py


    def prob(self, x=None, y=None, data=None,
             individually=True, dist=False, num_samples=1000):
        """Compute the probability of `y` given `x` and the model.

        TODO: docs...

        .. admonition:: Model must be fit first!

            Before calling :meth:`.prob` on a |Model|, you must first
            :meth:`.fit` it to some data.

        also, this should probably use log_prob, above, then exp it...

        Parameters
        ----------
        x : |ndarray| or |DataFrame| or int or str or list of str or int
            Independent variable values of the dataset to evaluate (aka the 
            "features").  If ``data`` was passed as a |DataFrame|, ``x`` can
            be an int or string or list of ints or strings specifying the 
            columns of that |DataFrame| to use as independent variables. If
            |None|,  will use the data the model was trained on (the default).
        y : |ndarray| or |DataFrame| or |Series| or int or str or list of str or int
            Dependent variable values of the dataset to evaluate (aka the 
            "target"). If ``data`` was passed as a |DataFrame|, ``y`` can be
            an int or string or list of ints or strings specifying the columns
            of that |DataFrame| to use as dependent variables. If |None|, 
            will use the data the model was trained on (the default).
        data : |None| or |DataFrame|
            Data to evaluate.  If ``data`` is |None|, it is assumed that
            ``x`` and ``y`` are |ndarray| or |DataFrame| or |Series|.  
            If ``data`` is a |DataFrame|, ``x`` and ``y`` are treated as
            strings or lists of strings containing the columns from
            ``data`` to use as in- and de-pendent variables.

        """

        # Check model has been fit
        self._ensure_is_fit()

        # Process input data
        x, y = process_xy_data(self, x, y, data)

        # TODO: evaluate log_prob w/ tf like in log_prob above


    def prob_by(self, x_by, x=None, y=None, data=None, bins=30, plot=True):
        """Plot the probability of observations `y` given `x` and the model
        as a function of independent variable(s) `x_by`.

        TODO: docs...

        .. admonition:: Model must be fit first!

            Before calling :meth:`.prob_by` on a |Model|, you must first
            :meth:`.fit` it to some data.

        Parameters
        ----------
        x_by : int or string or 2-element list of int or string
            Which independent variable(s) to plot the probability as a
            function of.  That is, which columns in ``x`` to plot by.
        x : |ndarray| or int or str or list of str or int
            Independent variable values of the dataset to fit (aka the 
            "features").  If ``data`` was passed as a |DataFrame|, ``x`` can be
            an int or string or list of ints or strings specifying the columns
            of that |DataFrame| to use as independent variables. If |None|, 
            will use the data the model was trained on (the default).
        y : |ndarray| or int or str or list of str or int
            Dependent variable values of the dataset to fit (aka the 
            "reponse"). If ``data`` was passed as a |DataFrame|, ``y`` can be
            an int or string or list of ints or strings specifying the columns
            of that |DataFrame| to use as independent variables. If |None|, 
            will use the data the model was trained on (the default).
        data : |None| or |DataFrame|
            DataFrame containing ``x`` and ``y``.  If ``data`` is |None|, 
            it is assumed that ``x`` and ``y`` are |ndarray|s.  If ``data`` 
            is a |DataFrame|, it is assumed that ``x`` and ``y`` are strings
            or lists of strings containing the columns from ``data`` to use.

        """

        # Check model has been fit
        self._ensure_is_fit()

        # Convert x_by to list of int
        x_by = self._int_x_by(x_by, x, y, data)

        # Compute the model posterior probability for each observation
        probs = self.prob(x, y)

        # Process input data
        x, y = process_xy_data(self, x, y, data)

        # Plot probability as a fn of x_by cols of x
        px, py = plot_by(x[:, x_by], probs, bins=bins, plot=plot)

        return px, py


    def cdf(self, x=None, y=None, data=None):
        """Compute the cumulative probability of `y` given `x` and the model.

        TODO: docs...

        .. admonition:: Model must be fit first!

            Before calling :meth:`.cdf` on a |Model|, you must first
            :meth:`.fit` it to some data.

        Parameters
        ----------
        x : |ndarray| or int or str or list of str or int
            Independent variable values of the dataset to fit (aka the 
            "features").  If ``data`` was passed as a |DataFrame|, ``x`` can be
            an int or string or list of ints or strings specifying the columns
            of that |DataFrame| to use as independent variables. If |None|, 
            will use the data the model was trained on (the default).
        y : |ndarray| or int or str or list of str or int
            Dependent variable values of the dataset to fit (aka the 
            "reponse"). If ``data`` was passed as a |DataFrame|, ``y`` can be
            an int or string or list of ints or strings specifying the columns
            of that |DataFrame| to use as independent variables. If |None|, 
            will use the data the model was trained on (the default).
        data : |None| or |DataFrame|
            DataFrame containing ``x`` and ``y``.  If ``data`` is |None|, 
            it is assumed that ``x`` and ``y`` are |ndarray|s.  If ``data`` 
            is a |DataFrame|, it is assumed that ``x`` and ``y`` are strings
            or lists of strings containing the columns from ``data`` to use.

        """

        # Check model has been fit
        self._ensure_is_fit()

        # Process input data
        x, y = process_xy_data(self, x, y, data)

        # TODO: same idea as log_prob above


    def cdf_by(self, x_by, x=None, y=None, data=None, bins=30):
        """Plot the cumulative probability of observations `y` given `x` and
        the model as a function of independent variable(s) `x_by`.

        TODO: docs...

        .. admonition:: Model must be fit first!

            Before calling :meth:`.cdf_by` on a |Model|, you must first
            :meth:`.fit` it to some data.

        Parameters
        ----------
        x_by : int or string or 2-element list of int or string
            Which independent variable(s) to plot the cumulative probability
            as a function of.  That is, which columns in ``x`` to plot by.
        x : |ndarray| or int or str or list of str or int
            Independent variable values of the dataset to fit (aka the 
            "features").  If ``data`` was passed as a |DataFrame|, ``x`` can be
            an int or string or list of ints or strings specifying the columns
            of that |DataFrame| to use as independent variables. If |None|, 
            will use the data the model was trained on (the default).
        y : |ndarray| or int or str or list of str or int
            Dependent variable values of the dataset to fit (aka the 
            "reponse"). If ``data`` was passed as a |DataFrame|, ``y`` can be
            an int or string or list of ints or strings specifying the columns
            of that |DataFrame| to use as independent variables. If |None|, 
            will use the data the model was trained on (the default).
        data : |None| or |DataFrame|
            DataFrame containing ``x`` and ``y``.  If ``data`` is |None|, 
            it is assumed that ``x`` and ``y`` are |ndarray|s.  If ``data`` 
            is a |DataFrame|, it is assumed that ``x`` and ``y`` are strings
            or lists of strings containing the columns from ``data`` to use.
        bins : TODO
        """

        # Check model has been fit
        self._ensure_is_fit()

        # Convert x_by to list of int
        x_by = self._int_x_by(x_by, x, y, data)

        # Compute the cumulative posterior probability for each observation
        probs = self.cdf(x, y)

        # Process input data
        x, y = process_xy_data(self, x, y, data)

        # Plot probability as a fn of x_by cols of x
        px, py = plot_by(x[:, x_by], probs, bins=bins, plot=plot)

        return px, py



class ContinuousDistribution(BaseDistribution):
    r"""Abstract base class for *continuous* ProbFlow |Distributions|

    TODO: More info...

    Methods
    -------

    :class:`.ContinuousDistribution` has all the same methods as 
    :class:`.BaseDistribution`:

    * :meth:`.fit`
    * :meth:`.predict`
    * :meth:`.metrics`
    * :meth:`.predictive_distribution`
    * :meth:`.plot_predictive_distribution`
    * :meth:`.posterior_mean`
    * :meth:`.posterior_sample`
    * :meth:`.posterior_plot`
    * :meth:`.prior_sample`
    * :meth:`.prior_plot`
    * :meth:`.posterior_plot_over_training`
    * :meth:`.posterior_plot_args_over_training`
    * :meth:`.prob`
    * :meth:`.prob_by`
    * :meth:`.log_prob`
    * :meth:`.log_prob_by`
    * :meth:`.cdf`
    * :meth:`.cdf_by`

    and in addition also has these methods:

    * :meth:`.predictive_prc`
    * :meth:`.confidence_intervals`
    * :meth:`.pred_dist_covered`
    * :meth:`.pred_dist_coverage`
    * :meth:`.coverage_by`
    * :meth:`.calibration_curve`
    * :meth:`.r_squared`
    * :meth:`.residuals`
    * :meth:`.residuals_plot`

    """


    def confidence_intervals(self, x=None, data=None,
                             prcs=[2.5, 97.5], num_samples=1000):
        """Compute confidence intervals on predictions for `x`.

        TODO: docs, prcs contains percentiles of predictive_distribution to use

        .. admonition:: Model must be fit first!

            Before calling :meth:`.confidence_intervals` on a |Model|, you must
            first :meth:`.fit` it to some data.

        Parameters
        ----------
        x : |ndarray| or int or str or list of str or int
            Independent variable values of the dataset to fit (aka the 
            "features").  If ``data`` was passed as a |DataFrame|, ``x`` can be
            an int or string or list of ints or strings specifying the columns
            of that |DataFrame| to use as independent variables. If |None|, 
            will use the data the model was trained on (the default).
        data : |None| or |DataFrame|
            DataFrame containing ``x``.  If ``data`` is |None|, 
            it is assumed that ``x`` is a |ndarray|.  If ``data`` 
            is a |DataFrame|, it is assumed that ``x`` is a string
            or list of strings containing the columns from ``data`` to use.
        prcs : list of float, or np.ndarray
            Percentiles to use as bounds of the confidence interval, between 0
            and 100.
            Default = [2.5, 97.5]
        num_samples : int
            Number of samples from the posterior predictive distribution to
            take to compute the confidence intervals.
            Default = 1000

        Returns
        -------
        conf_intervals : np.ndarray
            Confidence intervals on the predictions for samples in `x`.
        """

        # Check types
        # TODO

        # Check model has been fit
        self._ensure_is_fit()

        # Process input data
        x = process_data(self, x, data)

        # Compute percentiles of the predictive distribution
        pred_dist = self.predictive_distribution(x, num_samples=num_samples)
        return np.percentile(pred_dist, prcs)


    def predictive_prc(self, x=None, y=None, data=None, num_samples=1000):
        """Compute the percentile of each observation along the posterior
        predictive distribution.

        TODO: Docs...  Returns a percentile between 0 and 100

        .. admonition:: Model must be fit first!

            Before calling :meth:`.predictive_prc` on a |Model|, you must first
            :meth:`.fit` it to some data.

        Parameters
        ----------
        x : |ndarray| or int or str or list of str or int
            Independent variable values of the dataset to fit (aka the 
            "features").  If ``data`` was passed as a |DataFrame|, ``x`` can be
            an int or string or list of ints or strings specifying the columns
            of that |DataFrame| to use as independent variables. If |None|, 
            will use the data the model was trained on (the default).
        y : |ndarray| or int or str or list of str or int
            Dependent variable values of the dataset to fit (aka the 
            "reponse"). If ``data`` was passed as a |DataFrame|, ``y`` can be
            an int or string or list of ints or strings specifying the columns
            of that |DataFrame| to use as independent variables. If |None|, 
            will use the data the model was trained on (the default).
        data : |None| or |DataFrame|
            DataFrame containing ``x`` and ``y``.  If ``data`` is |None|, 
            it is assumed that ``x`` and ``y`` are |ndarray|s.  If ``data`` 
            is a |DataFrame|, it is assumed that ``x`` and ``y`` are strings
            or lists of strings containing the columns from ``data`` to use.
        """

        # Check model has been fit
        self._ensure_is_fit()

        # Check types
        if not isinstance(num_samples, int):
            raise TypeError('num_samples must be an int')
        if num_samples < 1:
            raise ValueError('num_samples must be positive')

        # Process input data
        x, y = process_xy_data(self, x, y, data)

        # Compute percentiles of the predictive distribution
        pred_dist = self.predictive_distribution(x, num_samples=num_samples)

        # Return percentiles of true y data along predictive distribution
        inds = np.argmax((np.sort(pred_dist, 0) >
                          y.reshape(1, x.shape[0], -1)),
                         axis=0)
        return inds/float(num_samples)

        # TODO: check for when true y value is above max pred_dist val!
        # I think argmax returns 0 when that's the case, which is
        # obviously not what we want


    def pred_dist_covered(self, x=None, y=None, data=None, prc=95.0):
        """Compute whether each observation was covered by the
        inner `prc` percentile of the posterior predictive
        distribution.

        TODO: Docs...

        .. admonition:: Model must be fit first!

            Before calling :meth:`.pred_dist_covered` on a |Model|, you must
            first :meth:`.fit` it to some data.

        Parameters
        ----------
        x : |ndarray| or int or str or list of str or int
            Independent variable values of the dataset to fit (aka the 
            "features").  If ``data`` was passed as a |DataFrame|, ``x`` can be
            an int or string or list of ints or strings specifying the columns
            of that |DataFrame| to use as independent variables. If |None|, 
            will use the data the model was trained on (the default).
        y : |ndarray| or int or str or list of str or int
            Dependent variable values of the dataset to fit (aka the 
            "reponse"). If ``data`` was passed as a |DataFrame|, ``y`` can be
            an int or string or list of ints or strings specifying the columns
            of that |DataFrame| to use as independent variables. If |None|, 
            will use the data the model was trained on (the default).
        data : |None| or |DataFrame|
            DataFrame containing ``x`` and ``y``.  If ``data`` is |None|, 
            it is assumed that ``x`` and ``y`` are |ndarray|s.  If ``data`` 
            is a |DataFrame|, it is assumed that ``x`` and ``y`` are strings
            or lists of strings containing the columns from ``data`` to use.
        """

        # Check types
        if not isinstance(prc, float):
            if isinstance(prc, int):
                prc = float(prc)
            else:
                raise TypeError('prc must be a float')
        if prc < 0 or prc > 100:
            raise ValueError('prc must be between 0 and 100')

        # Check model has been fit
        self._ensure_is_fit()

        # Compute the predictive percentile of each observation
        pred_prcs = self.predictive_prc(x, y, data)

        # Determine what samples fall in the inner prc percentile
        lb = 0.01*(100.0-prc)/2.0
        ub = 0.01*(100.0-lb)
        return (pred_prcs>=lb) & (pred_prcs<ub)


    def pred_dist_coverage(self, x=None, y=None, data=None, prc=95.0):
        """Compute what percent of samples are covered by the inner `prc`
        percentile of the posterior predictive distribution.

        TODO: Docs...
        returns a scalar (from 0 to 100)

        .. admonition:: Model must be fit first!

            Before calling :meth:`.pred_dist_coverage` on a |Model|, you must
            first :meth:`.fit` it to some data.

        Parameters
        ----------
        x : |ndarray| or int or str or list of str or int
            Independent variable values of the dataset to fit (aka the 
            "features").  If ``data`` was passed as a |DataFrame|, ``x`` can be
            an int or string or list of ints or strings specifying the columns
            of that |DataFrame| to use as independent variables. If |None|, 
            will use the data the model was trained on (the default).
        y : |ndarray| or int or str or list of str or int
            Dependent variable values of the dataset to fit (aka the 
            "reponse"). If ``data`` was passed as a |DataFrame|, ``y`` can be
            an int or string or list of ints or strings specifying the columns
            of that |DataFrame| to use as independent variables. If |None|, 
            will use the data the model was trained on (the default).
        data : |None| or |DataFrame|
            DataFrame containing ``x`` and ``y``.  If ``data`` is |None|, 
            it is assumed that ``x`` and ``y`` are |ndarray|s.  If ``data`` 
            is a |DataFrame|, it is assumed that ``x`` and ``y`` are strings
            or lists of strings containing the columns from ``data`` to use.
        """

        # Check model has been fit
        self._ensure_is_fit()

        # Compute whether each sample was covered by the predictive interval
        covered = self.pred_dist_covered(x, y, data, prc)

        # Return the percentage of samples which were covered
        return 100*covered.mean()


    def coverage_by(self, x_by=0, x=None, y=None, data=None, 
                    prc=95.0, bins=30, plot=True,
                    true_line_kwargs={}, ideal_line_kwargs={}):
        """Compute and plot the coverage of the inner `prc`
        percentile of the posterior predictive distribution as a
        function of specified independent variables.

        TODO: Docs...

        .. admonition:: Model must be fit first!

            Before calling :meth:`.coverage_by` on a |Model|, you must first
            :meth:`.fit` it to some data.


        Parameters
        ----------
        x_by : int or string or 2-element list of int or string
            Which independent variable(s) to plot the coverage as a
            function of.  That is, which columns in ``x`` to plot by.
            Default is to use the first column in ``x``.
        x : |ndarray| or int or str or list of str or int
            Independent variable values of the dataset to fit (aka the 
            "features").  If ``data`` was passed as a |DataFrame|, ``x`` can be
            an int or string or list of ints or strings specifying the columns
            of that |DataFrame| to use as independent variables. If |None|, 
            will use the data the model was trained on (the default).
        y : |ndarray| or int or str or list of str or int
            Dependent variable values of the dataset to fit (aka the 
            "reponse"). If ``data`` was passed as a |DataFrame|, ``y`` can be
            an int or string or list of ints or strings specifying the columns
            of that |DataFrame| to use as independent variables. If |None|, 
            will use the data the model was trained on (the default).
        data : |None| or |DataFrame|
            DataFrame containing ``x`` and ``y``.  If ``data`` is |None|, 
            it is assumed that ``x`` and ``y`` are |ndarray|s.  If ``data`` 
            is a |DataFrame|, it is assumed that ``x`` and ``y`` are strings
            or lists of strings containing the columns from ``data`` to use.
        prc : float between 0 and 100
            Inner percentile to find the coverage of.  For example, if 
            ``prc=95``, will compute the coverage of the inner 95% of the 
            posterior predictive distribution.
        bins : int
            Number of bins to use for x_by
        plot : bool
            Whether to plot the coverage.  Default = True
        true_line_kwargs : dict
            Dict to pass to matplotlib.pyplot.plot for true coverage line
        ideal_line_kwargs : dict
            Dict of args to pass to matplotlib.pyplot.plot for ideal coverage
            line.


        Returns
        -------
        xo : |ndarray|
            Values of x_by corresponding to bin centers.
        co : |ndarray|
            Coverage of the inner ``prc`` of the predictive distribution in 
            each bin.
        """

        # Check model has been fit
        self._ensure_is_fit()

        # Convert x_by to list of int
        x_by = self._int_x_by(x_by, x, y, data)

        # Compute whether each sample was covered by the predictive interval
        covered = self.pred_dist_covered(x, y, data, prc)

        # Process input data
        x, y = process_xy_data(self, x, y, data)

        # Plot coverage proportion as a fn of x_by cols of x
        xo, co = plot_by(x[:, x_by], 100*covered, bins=bins,
                         plot=plot, label='Actual', **true_line_kwargs)

        # Line kwargs
        if 'linestyle' not in ideal_line_kwargs:
            ideal_line_kwargs['linestyle'] = '--'
        if 'color' not in ideal_line_kwargs:
            ideal_line_kwargs['color'] = 'k'

        # Also plot ideal line
        if plot and isinstance(x_by, int):
            plt.axhline(prc, label='Ideal', **ideal_line_kwargs)
            plt.legend()
            plt.ylabel(str(prc)+'% predictive interval coverage')
            plt.xlabel('Value of '+str(x_by))

        return xo, co


    def calibration_curve(self, x=None, y=None, data=None,
                          split_by=None, bins=10, plot=False):
        """Plot and/or return calibration curve.

        Plots and returns the calibration curve (the percentile of the posterior
        predictive distribution on the x-axis, and the percent of samples which
        actually fall into that range on the y-axis).

        .. admonition:: Model must be fit first!

            Before calling
            :meth:`calibration_curve() <.ContinuousDistribution.calibration_curve>`
            on a |Model|, you must first 
            :meth:`fit() <.BaseDistribution.fit>`
            it to some data.

        Parameters
        ----------
        x : |ndarray| or int or str or list of str or int
            Independent variable values of the dataset to fit (aka the 
            "features").  If ``data`` was passed as a |DataFrame|, ``x`` can be
            an int or string or list of ints or strings specifying the columns
            of that |DataFrame| to use as independent variables. If |None|, 
            will use the data the model was trained on (the default).
        y : |ndarray| or int or str or list of str or int
            Dependent variable values of the dataset to fit (aka the 
            "reponse"). If ``data`` was passed as a |DataFrame|, ``y`` can be
            an int or string or list of ints or strings specifying the columns
            of that |DataFrame| to use as independent variables. If |None|, 
            will use the data the model was trained on (the default).
        data : |None| or |DataFrame|
            DataFrame containing ``x`` and ``y``.  If ``data`` is |None|, 
            it is assumed that ``x`` and ``y`` are |ndarrays| .  If ``data`` 
            is a |DataFrame|, it is assumed that ``x`` and ``y`` are strings
            or lists of strings containing the columns from ``data`` to use.
        split_by : int
            Draw the calibration curve independently for datapoints
            with each unique value in `x[:,split_by]` (a categorical
            column).
        bins : int, list of float, or |ndarray|
            Bins used to compute the curve.  If an integer, will use
            `bins` evenly-spaced bins from 0 to 1.  If a vector,
            `bins` is the vector of bin edges.

        Returns
        -------
        cx : |ndarray|
            Vector of percentiles (the middle of each percentile
            bin).  Length is determined by `bins`.
        cy : |ndarray|
            Vector of percentages of samples which fell within each
            percentile bin of the posterior predictive distribution.

        See Also
        --------
        predictive_distribution : used to generate the posterior
            predictive distribution.

        Notes
        -----
        TODO: Docs...

        Examples
        --------
        TODO: Docs...

        """

        # Check model has been fit
        self._ensure_is_fit()

        #TODO
        pass


    def r_squared(self, x=None, y=None, data=None, 
                  num_samples=1000, plot=False):
        """Compute the Bayesian R-squared value.

        Compute the Bayesian R-squared distribution :ref:`[1] <ref_r_squared>`.
        TODO: more info and docs...

        .. admonition:: Model must be fit first!

            Before calling :meth:`.r_squared` on a |Model|, you must
            first :meth:`.fit` it to some data.

        Parameters
        ----------
        x : |ndarray| or int or str or list of str or int
            Independent variable values of the dataset to fit (aka the 
            "features").  If ``data`` was passed as a |DataFrame|, ``x`` can be
            an int or string or list of ints or strings specifying the columns
            of that |DataFrame| to use as independent variables. If |None|, 
            will use the data the model was trained on (the default).
        y : |ndarray| or int or str or list of str or int
            Dependent variable values of the dataset to fit (aka the 
            "reponse"). If ``data`` was passed as a |DataFrame|, ``y`` can be
            an int or string or list of ints or strings specifying the columns
            of that |DataFrame| to use as independent variables. If |None|, 
            will use the data the model was trained on (the default).
        data : |None| or |DataFrame|
            DataFrame containing ``x`` and ``y``.  If ``data`` is |None|, 
            it is assumed that ``x`` and ``y`` are |ndarray|s.  If ``data`` 
            is a |DataFrame|, it is assumed that ``x`` and ``y`` are strings
            or lists of strings containing the columns from ``data`` to use.
        num_samples : int
            Number of posterior draws to use for computing the r-squared
            distribution.  Default = `1000`.
        plot : bool
            Whether to plot the r-squared distribution

        Returns
        -------
        |ndarray|
            Samples from the r-squared distribution.  Size: ``(num_samples,)``.

        Notes
        -----
        TODO: Docs...

        Examples
        --------
        TODO: Docs...

        References
        ----------
        .. _ref_r_squared:
        .. [1] Andrew Gelman, Ben Goodrich, Jonah Gabry, & Aki Vehtari.
            R-squared for Bayesian regression models.
            *The American Statistician*, 2018.
            https://doi.org/10.1080/00031305.2018.1549100
        """
        #TODO
        pass


    def residuals(self, x=None, y=None, data=None):
        """Compute the residuals of the model's predictions.

        TODO: docs...

        Parameters
        ----------
        x : |ndarray| or int or str or list of str or int
            Independent variable values of the dataset to fit (aka the 
            "features").  If ``data`` was passed as a |DataFrame|, ``x`` can be
            an int or string or list of ints or strings specifying the columns
            of that |DataFrame| to use as independent variables. If |None|, 
            will use the data the model was trained on (the default).
        y : |ndarray| or int or str or list of str or int
            Dependent variable values of the dataset to fit (aka the 
            "reponse"). If ``data`` was passed as a |DataFrame|, ``y`` can be
            an int or string or list of ints or strings specifying the columns
            of that |DataFrame| to use as independent variables. If |None|, 
            will use the data the model was trained on (the default).
        data : |None| or |DataFrame|
            DataFrame containing ``x`` and ``y``.  If ``data`` is |None|, 
            it is assumed that ``x`` and ``y`` are |ndarray|s.  If ``data`` 
            is a |DataFrame|, it is assumed that ``x`` and ``y`` are strings
            or lists of strings containing the columns from ``data`` to use.

        """
        # TODO
        pass


    def residuals_plot(self, x=None, y=None, data=None):
        """Plot the distribution of residuals of the model's predictions.

        TODO: docs...

        Parameters
        ----------
        x : |ndarray| or |DataFrame| or int or str or list of str or int
            Independent variable values of the dataset to fit (aka the 
            "features").  If ``data`` was passed as a |DataFrame|, ``x`` can be
            an int or string or list of ints or strings specifying the columns
            of that |DataFrame| to use as independent variables. If |None|, 
            will use the data the model was trained on (the default).
        y : |ndarray| or |DataFrame| or |Series| or int or str or list of str or int
            Dependent variable values of the dataset to fit (aka the 
            "reponse"). If ``data`` was passed as a |DataFrame|, ``y`` can be
            an int or string or list of ints or strings specifying the columns
            of that |DataFrame| to use as independent variables. If |None|, 
            will use the data the model was trained on (the default).
        data : |None| or |DataFrame|
            DataFrame containing ``x`` and ``y``.  If ``data`` is |None|, 
            it is assumed that ``x`` and ``y`` are |ndarray|s.  If ``data`` 
            is a |DataFrame|, it is assumed that ``x`` and ``y`` are strings
            or lists of strings containing the columns from ``data`` to use.

        """
        # TODO
        pass



class DiscreteDistribution(BaseDistribution):
    r"""Abstract base class for *discrete* ProbFlow |Distributions|

    TODO: More info...

    Methods
    -------

    :class:`.DiscreteDistribution` has all the same methods as 
    :class:`.BaseDistribution`:

    * :meth:`.fit`
    * :meth:`.predict`
    * :meth:`.metrics`
    * :meth:`.predictive_distribution`
    * :meth:`.plot_predictive_distribution`
    * :meth:`.posterior_mean`
    * :meth:`.posterior_sample`
    * :meth:`.posterior_plot`
    * :meth:`.prior_sample`
    * :meth:`.prior_plot`
    * :meth:`.posterior_plot_over_training`
    * :meth:`.posterior_plot_args_over_training`
    * :meth:`.prob`
    * :meth:`.prob_by`
    * :meth:`.log_prob`
    * :meth:`.log_prob_by`
    * :meth:`.cdf`
    * :meth:`.cdf_by`

    and in addition also has this method:

    * :meth:`.calibration_curve`

    """

    def predict(self, x=None, data=None):
        """Predict discrete dependent variable for independent var samples in x.

        TODO: explain how predictions are generated using the MODE of each
        variational distribution

        .. admonition:: Model must be fit first!

            Before calling :meth:`.predict` on a |Model|, you must first
            :meth:`.fit` it to some data.

        Parameters
        ----------
        x : |ndarray| or int or str or list of str or int
            Independent variable values of the dataset to fit (aka the 
            "features").  If ``data`` was passed as a |DataFrame|, ``x`` can be
            an int or string or list of ints or strings specifying the columns
            of that |DataFrame| to use as independent variables. If |None|, 
            will use the data the model was trained on (the default).
        data : |None| or |DataFrame|
            DataFrame containing ``x``.  If ``data`` is |None|, 
            it is assumed that ``x`` is a |ndarray|.  If ``data`` 
            is a |DataFrame|, it is assumed that ``x`` is a string
            or list of strings containing the columns from ``data`` to use.

        Returns
        -------
        |ndarray|
            Predicted y-value for each sample in ``x``.  Will be of
            size ``(N, D_out)``, where N is the number of samples (equal
            to ``x.shape[0]``) and D_out is the number of output
            dimensions (equal to ``y.shape[1:]``).

        Examples
        --------
        TODO: Docs...

        """

        # Check model has been fit
        self._ensure_is_fit()

        # Process data
        x = process_data(self, x, data)

        # Predict using the mode of the mean model
        return self._session.run(
            self.mean_obj.mode(), 
            feed_dict={self._ph['x']: x,
                       self._ph['batch_size']: [x.shape[0]]})


    def calibration_curve(self, x=None, y=None, data=None,
                          split_by=None, bins=10):
        """Plot and return calibration curve.

        Plots and returns the calibration curve (estimated
        probability of outcome vs the true probability of that
        outcome).

        .. admonition:: Model must be fit first!

            Before calling
            :meth:`calibration_curve() <.CategoricalModel.calibration_curve>`
            on a |Model|, you must first :meth:`.fit` it to some data.

        Parameters
        ----------
        x : |ndarray| or int or str or list of str or int
            Independent variable values of the dataset to fit (aka the 
            "features").  If ``data`` was passed as a |DataFrame|, ``x`` can be
            an int or string or list of ints or strings specifying the columns
            of that |DataFrame| to use as independent variables. If |None|, 
            will use the data the model was trained on (the default).
        y : |ndarray| or int or str or list of str or int
            Dependent variable values of the dataset to fit (aka the 
            "reponse"). If ``data`` was passed as a |DataFrame|, ``y`` can be
            an int or string or list of ints or strings specifying the columns
            of that |DataFrame| to use as independent variables. If |None|, 
            will use the data the model was trained on (the default).
        data : |None| or |DataFrame|
            DataFrame containing ``x`` and ``y``.  If ``data`` is |None|, 
            it is assumed that ``x`` and ``y`` are |ndarray|s.  If ``data`` 
            is a |DataFrame|, it is assumed that ``x`` and ``y`` are strings
            or lists of strings containing the columns from ``data`` to use.
        split_by : int or str
            Draw curve independently for datapoints with each unique value in 
            this categorical column number.
        bins : int or list of float or |ndarray|
            Number of bins used to compute the curve.  An integer to
            specify the number of evenly-spaced bins from 0 to
            1, or a list or array-like to specify the bin edges.

        #TODO: split by continuous cols as well? Then will need to define bins or edges too

        TODO: Docs...

        """

        # Check model has been fit
        self._ensure_is_fit()

        #TODO
        pass
