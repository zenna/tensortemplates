import tensorflow as tf
import numpy as np
from tensortemplates.util import *


def consistent_batch_size(shapes):
    """Are the batch sizes the same"""
    return same([shape[0] for shape in shapes])


def batch_flatten(t):
    """Reshape tensor so that it is flat vector (except for batch dimension)"""
    return tf.reshape(t, [tf.shape(t)[0], -1])


def template_dict(inputs, inp_shapes, out_shapes, **kwargs):
    input_list = list(inputs.values())
    inp_shapes_list = list(inp_shapes.values())
    out_shapes_list = list(out_shapes.values())
    outputs, params = template(input_list, inp_shapes_list, out_shapes_list, **kwargs)
    return dict(zip(out_shapes.keys(), outputs)), params


def reshape_input(inp_shapes):
    flat_input_shapes = [np.prod(inp_shape[1:]) for inp_shape in inp_shapes]
    input_width = np.sum(flat_input_shapes)

    flat_output_shapes = [np.prod(out_shape[1:]) for out_shape in out_shapes]
    output_width = np.sum(flat_output_shapes)

    # Num inputs and outputs
    ninputs = len(inp_shapes)
    noutputs = len(out_shapes)

    flat_inputs = [batch_flatten(inp) for inp in inputs]
    x = tf.concat(1, flat_inputs)
    return x, flat_input_shapes


def batch_norm(x):
    return x


def layer(x, inp_width, out_width, sfx, nl=tf.nn.relu,
          W_init=None, b_init=tf.zeros_initializer, layer_norm=False):
    """Neural Network Layer - nl(Wx+b)"""
    with tf.name_scope("layer"):
        W = tf.get_variable(name="W_%s" % sfx, shape=(inp_width, out_width),
                            initializer=W_init)
        b = tf.get_variable(name="b_%s" % sfx, shape=(out_width),
                            initializer=b_init)
        mmbias = tf.matmul(x, W) + b
        # mmbias = tf.Print(mmbias, [mmbias], message="mmbias")
        if layer_norm:
            mmbias = tf.contrib.layers.layer_norm(mmbias)
        # mmbias = tf.Print(mmbias, [mmbias], message="lnmmbias")
        op = nl(mmbias, name='op_%s' % sfx)
    return op


def flat_shape(shape):
    """Return the flattened shape of a tensor"""
    return np.prod(shape[1:])


def width(shapes):
    flat_shapes = [flat_shape(shape) for shape in shapes]
    return np.sum(flat_shapes)


def sliceup(t, shapes):
    """Slice and reshape a flat input (batch_size, n) to list of tensors"""
    with tf.name_scope("sliceup"):
        noutputs = len(shapes)
        outputs = []
        lb = 0
        flat_shapes = [flat_shape(shape) for shape in shapes]
        for i in range(noutputs):
            ub = lb + flat_shapes[i]
            out = t[:, lb:ub]
            # import pdb; pdb.set_trace()
            new_shape = (tf.shape(out)[0],) + shapes[i][1:]
            rout = tf.reshape(out, new_shape)
            outputs.append(rout)
            lb = ub
    return outputs


def template(inputs, inp_shapes, out_shapes, **kwargs):
    """
    Residual neural network
    inputs : [tf.Tensor/tf.Variable] - inputs to be transformed
    out_shapes : (tf.TensorShape) | (Int) - shapes of output of tensor (includes batch_size)
    """
    ## Meta Parameters
    layer_width = kwargs['layer_width']
    nblocks = kwargs['nblocks']
    block_size = kwargs['block_size']

    ## Handle Reshaping (res_net expects input as vector)
    print("Input Shapes to Resnet", inp_shapes)
    print("Output Shapes to Resnet", out_shapes)
    assert consistent_batch_size(inp_shapes + out_shapes), "Batch sizes differ"
    input_width = width(inp_shapes)
    output_width = width(out_shapes)

    # Num inputs and outputs
    flat_inputs = [batch_flatten(inp) for inp in inputs]
    prev_layer = tf.concat(1, flat_inputs)

    ## Layers
    ## ======

    ## Input Projection
    if nblocks > 1:
        if layer_width != input_width:
            print("Input projection, layer_width: %s input_width: %s" % (layer_width, input_width))
            wx_sfx = 'wxinpproj'
            wx = layer(prev_layer, input_width, layer_width, wx_sfx)
        else:
            print("Skipping input weight projection, layer_width: %s input_width: %s" % (layer_width, input_width))
            wx = prev_layer

    # On first layer only prev_layer_width = input_width
    prev_layer_width = input_width
    # prev_layer = tf.Print(prev_layer, [prev_layer], message="resnetinp")
    ## Residual Blocks
    for j in range(nblocks):
        with tf.name_scope("residual_block"):
            for i in range(block_size):
                print("IJ",i," ", j)
                sfx = "%s_%s" % (j, i)
                prev_layer = output = layer(prev_layer, prev_layer_width,
                                            layer_width, sfx)

                 # On all other layers prev_layer_width = layer_width
                prev_layer_width = layer_width
            if nblocks > 1:
                prev_layer = wx = prev_layer + wx

    ## Project output to correct width
    if layer_width != output_width:
        print("Output projection, layer_width: %s output_width: %s" % (layer_width, output_width))
        wx_sfx = 'wxoutproj'
        prev_layer = layer(prev_layer, layer_width, output_width, wx_sfx)
    else:
        print("Skipping output projection, layer_width: %s output_width: %s" % (layer_width, output_width))

    ## Unconcatenate output and separate
    outputs = sliceup(prev_layer, out_shapes)
    params = []
    return outputs, params


def kwargs():
    """Return (default) arguments for a residual network"""
    options = {}
    options['nblocks'] = (int, 1)
    options['block_size'] = (int, 1)
    options['layer_width'] = (int, 50)
    return options
