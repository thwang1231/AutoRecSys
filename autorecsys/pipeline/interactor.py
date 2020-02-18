from __future__ import absolute_import, division, print_function, unicode_literals

import tensorflow as tf
from tensorflow.python.util import nest
from autorecsys.pipeline.base import Block
from tensorflow.keras.layers import Dense, Input, Concatenate
import random

# numberList = [111,222,333,444,555]
# print("random item from list is: ", random.choice(numberList))


class RandomSelectInteraction(Block):
        """
        ConcatenateInteraction
        """
        def __init__(self, **kwargs):
            super().__init__(**kwargs)

        def get_state(self):
            state = super().get_state()
            return state

        def set_state(self, state):
            super().set_state(state)

        def build(self, hp, inputs=None):
            output_node = nest.flatten(inputs)
            output_node = random.choice(output_node)
            return output_node


class ConcatenateInteraction(Block):
        """
        ConcatenateInteraction
        """
        def __init__(self, **kwargs):
            super().__init__(**kwargs)

        def get_state(self):
            state = super().get_state()
            return state

        def set_state(self, state):
            super().set_state(state)

        def build(self, hp, inputs=None):
            inputs = nest.flatten(inputs)
            output_node = tf.concat( inputs, axis = 1 )
            return output_node


class ElementwiseInteraction(Block):
    """
    ElementwiseInteraction
    """
    def __init__(self,
                 elementwise_type=None,
                 **kwargs):
        super().__init__(**kwargs)
        self.elementwise_type = elementwise_type

    def get_state(self):
        state = super().get_state()
        state.update({
            'elementwise_type': self.elementwise_type})
        return state

    def set_state(self, state):
        super().set_state(state)
        self.elementwise_type = state['elementwise_type']


    def build(self, hp, inputs=None):
        input_node = nest.flatten(inputs)

        shape_set = set()
        for input in input_node:
            shape_set.add( input.shape[1] )
        if  len(shape_set) > 1:
            raise ValueError("Inputs of ElementwiseInteraction should have same dimension.")

        elementwise_type = self.elementwise_type or hp.Choice('elementwise_type',
                                                                ["sum", "average", "innerporduct" ],
                                                                default='average')
        if elementwise_type == "sum":
            output_node = tf.add_n( input_node )
        elif elementwise_type == "average":
            output_node = tf.reduce_mean(input_node, axis=0)
        elif elementwise_type == "innerporduct":
            output_node = tf.reduce_prod( input_node, axis=0 )
        else:
            output_node = tf.add_n(input_node)
        return output_node

class InteractingLayer(Layer):
    """
    """

    def __init__(self, att_embedding_size=8, head_num=2, use_res=True, seed=1024, **kwargs):
        if head_num <= 0:
            raise ValueError('head_num must be a int > 0')
        self.att_embedding_size = att_embedding_size
        self.head_num = head_num
        self.use_res = use_res
        self.seed = seed
        super(InteractingLayer, self).__init__(**kwargs)

    def build(self, input_shape):
        if len(input_shape) != 3:
            raise ValueError(
                "Unexpected inputs dimensions %d, expect to be 3 dimensions" % (len(input_shape)))
        embedding_size = int(input_shape[-1])
        self.W_Query = self.add_weight(name='query', shape=[embedding_size, self.att_embedding_size * self.head_num],
                                       dtype=tf.float32,
                                       initializer=tf.keras.initializers.TruncatedNormal(seed=self.seed))
        self.W_key = self.add_weight(name='key', shape=[embedding_size, self.att_embedding_size * self.head_num],
                                     dtype=tf.float32,
                                     initializer=tf.keras.initializers.TruncatedNormal(seed=self.seed + 1))
        self.W_Value = self.add_weight(name='value', shape=[embedding_size, self.att_embedding_size * self.head_num],
                                       dtype=tf.float32,
                                       initializer=tf.keras.initializers.TruncatedNormal(seed=self.seed + 2))
        if self.use_res:
            self.W_Res = self.add_weight(name='res', shape=[embedding_size, self.att_embedding_size * self.head_num],
                                         dtype=tf.float32,
                                         initializer=tf.keras.initializers.TruncatedNormal(seed=self.seed))

        # Be sure to call this somewhere!
        super(InteractingLayer, self).build(input_shape)

    def call(self, inputs, **kwargs):
        if K.ndim(inputs) != 3:
            raise ValueError(
                "Unexpected inputs dimensions %d, expect to be 3 dimensions" % (K.ndim(inputs)))

        querys = tf.tensordot(inputs, self.W_Query,
                              axes=(-1, 0))  # None F D*head_num
        keys = tf.tensordot(inputs, self.W_key, axes=(-1, 0))
        values = tf.tensordot(inputs, self.W_Value, axes=(-1, 0))

        # head_num None F D
        querys = tf.stack(tf.split(querys, self.head_num, axis=2))
        keys = tf.stack(tf.split(keys, self.head_num, axis=2))
        values = tf.stack(tf.split(values, self.head_num, axis=2))

        inner_product = tf.matmul(
            querys, keys, transpose_b=True)  # head_num None F F
        self.normalized_att_scores = softmax(inner_product)

        result = tf.matmul(self.normalized_att_scores,
                           values)  # head_num None F D
        result = tf.concat(tf.split(result, self.head_num, ), axis=-1)
        result = tf.squeeze(result, axis=0)  # None F D*head_num

        if self.use_res:
            result += tf.tensordot(inputs, self.W_Res, axes=(-1, 0))
        result = tf.nn.relu(result)

        return result

    def compute_output_shape(self, input_shape):

        return (None, input_shape[1], self.att_embedding_size * self.head_num)

    def get_config(self, ):
        config = {'att_embedding_size': self.att_embedding_size, 'head_num': self.head_num, 'use_res': self.use_res,
                  'seed': self.seed}
        base_config = super(InteractingLayer, self).get_config()
        return dict(list(base_config.items()) + list(config.items()))

class MLPInteraction(Block):
    """
    multi-layer perceptron interactor
    """
    def __init__(self,
                 units=None,
                 num_layers=None,
                 use_batchnorm=None,
                 dropout_rate=None,
                 **kwargs):
        super().__init__(**kwargs)
        self.fixed_params = []
        self.tunable_candidates = ['units', 'num_layers', 'use_batchnorm', 'dropout_rate']
        self.units = units
        self.num_layers = num_layers
        self.use_batchnorm = use_batchnorm
        self.dropout_rate = dropout_rate
        # self._check_fixed()
        # self._hyperparameters = self._get_hyperparameters()

    def get_state(self):
        state = super().get_state()
        state.update({
            'units': self.units,
            'num_layers': self.num_layers,
            'use_batchnorm': self.use_batchnorm,
            'dropout_rate': self.dropout_rate})
        return state

    def set_state(self, state):
        super().set_state(state)
        self.units = state['units']
        self.num_layers = state['num_layers']
        self.use_batchnorm = state['use_batchnorm']
        self.dropout_rate = state['dropout_rate']

    def build(self, hp, inputs=None):
        inputs = nest.flatten(inputs)
        input_node = tf.concat(inputs, axis=1)
        output_node = input_node
        num_layers = self.num_layers or hp.Choice('num_layers', [1, 2, 3], default=2)
        use_batchnorm = self.use_batchnorm
        if use_batchnorm is None:
            use_batchnorm = hp.Choice('use_batchnorm', [True, False], default=False)
        dropout_rate = self.dropout_rate or hp.Choice('dropout_rate',
                                                      [0.0, 0.25, 0.5],
                                                      default=0)

        for i in range(num_layers):
            units = self.units or hp.Choice(
                'units_{i}'.format(i=i),
                [16, 32, 64, 128, 256, 512, 1024],
                default=32)

            output_node = tf.keras.layers.Dense(units)(output_node)
            if use_batchnorm:
                output_node = tf.keras.layers.BatchNormalization()(output_node)
            output_node = tf.keras.layers.ReLU()(output_node)
            output_node = tf.keras.layers.Dropout(dropout_rate)(output_node)
        return output_node


class HyperInteraction(Block):
    """Combination of serveral interactor into one.
    # Arguments
    meta_interator_num: int
    interactor_type: interactor_name
    """
    def __init__(self, meta_interator_num=None, interactor_type=None, **kwargs):
        super().__init__(**kwargs)
        self.meta_interator_num = meta_interator_num
        self.interactor_type = interactor_type

    def get_state(self):
        state = super().get_state()
        state.update({
            'interactor_type': self.interactor_type,
            'meta_interator_num': self.meta_interator_num
        })
        return state

    def set_state(self, state):
        super().set_state(state)
        self.interactor_type = state['interactor_type']
        self.meta_interator_num = state['meta_interator_num']

    def build(self, hp, inputs=None):
        inputs = nest.flatten(inputs)
        meta_interator_num =  self.meta_interator_num or hp.Choice('meta_interator_num',
                                                                    [1, 2, 3, 4, 5, 6],
                                                                    default=3)
        # inputs = tf.keras.backend.repeat(inputs, n=meta_interator_num)
        # interactors_name = ["MLPInteraction"]
        interactors_name = []
        for i in range( meta_interator_num ):
            tmp_interactor_type = self.interactor_type or hp.Choice('interactor_type_' + str(i),
                                                                    [ "MLPInteraction", "ConcatenateInteraction", "RandomSelectInteraction"],
                                                                    default='ConcatenateInteraction')
            interactors_name.append(tmp_interactor_type)


        print( "interactors_name", interactors_name )
        outputs = []
        for i, interactor_name in enumerate( interactors_name ):
            if interactor_name == "MLPInteraction":
                ##TODO: support intra block hyperparameter tuning
                output_node = MLPInteraction().build(hp, inputs)
                outputs.append(output_node)

            if interactor_name == "ConcatenateInteraction":
                output_node = ConcatenateInteraction().build(hp, inputs)
                outputs.append(output_node)

            if interactor_name == "RandomSelectInteraction":
                output_node = RandomSelectInteraction().build(hp, inputs)
                outputs.append(output_node)

        outputs = tf.concat(outputs, axis=1)
        # ConcatenateInteraction().build(hp, inputs)
        return outputs



class CrossNetInteraction(Block):
    """

    """
    def __init__(self, layer_num=2, l2_reg=0, seed=1024, **kwargs):
        self.layer_num = layer_num
        self.l2_reg = l2_reg
        self.seed = seed
        super().__init__(**kwargs)

    def get_state(self):
        state = super().get_state()
        return state

    def set_state(self, state):
        super().set_state(state)


    def build(self, hp, inputs=None):
        input_node = tf.concat(inputs, axis=1)
        if len(input_node.shape) != 2:
            raise ValueError(
                "Unexpected inputs dimensions %d, expect to be 2 dimensions" % len(input_node.shape))

        dim = int(input_node.shape[-1])
        self.kernels = [self.add_weight(name='kernel' + str(i),
                                        shape=(dim, 1),
                                        initializer=glorot_normal(
                                            seed=self.seed),
                                        regularizer=l2(self.l2_reg),
                                        trainable=True) for i in range(self.layer_num)]
        self.bias = [self.add_weight(name='bias' + str(i),
                                     shape=(dim, 1),
                                     initializer=Zeros(),
                                     trainable=True) for i in range(self.layer_num)]
        output_node = input_node
        x_0 = tf.expand_dims(input_node, axis=2)
        x_l = x_0
        for i in range(self.layer_num):
            xl_w = tf.tensordot(x_l, self.kernels[i], axes=(1, 0))
            dot_ = tf.matmul(x_0, xl_w)
            x_l = dot_ + self.bias[i] + x_l
        output_node = tf.squeeze(x_l, axis=2)
        return output_node 


class FMInteraction(Block):
    """
    factorization machine interactor
    """

    def __init__(self,
                 embedding_dim=None,
                 **kwargs):
        super().__init__(**kwargs)
        self.fixed_params = []
        self.tunable_candidates = ['embedding_dim']
        self.embedding_dim = embedding_dim

    def get_state(self):
        state = super().get_state()
        state.update(
            {
                'embedding_dim': self.embedding_dim,
            })
        return state

    def set_state(self, state):
        super().set_state(state)
        self.embedding_dim = state['embedding_dim']

    def build(self, hp, inputs=None):
        embedding_dim = self.embedding_dim or hp.Choice('embedding_dim', [8, 16], default=8)

        # TODO: align embedding_dim if not the same
        input_node = tf.concat(inputs, axis=1)
        if len(input_node.shape) != 3:
            raise ValueError(
                "Unexpected inputs dimensions %d, expect to be 3 dimensions" % len(input_node.shape)
            )

        output_node = input_node
        square_of_sum = tf.square(tf.reduce_sum(output_node, axis=1, keepdims=True))
        sum_of_square = tf.reduce_sum(output_node * output_node, axis=1, keepdims=True)
        cross_term = square_of_sum - sum_of_square
        output_node = 0.5 * tf.reduce_sum(cross_term, axis=2, keepdims=False)

        return output_node
