from __future__ import print_function
import os
import datetime
import numpy as np
import tensorflow as tf
from six.moves import xrange

import Batch_manager_5channels as dataset
import data_reader_5channels as reader
import tensor_utils_5_channels as utils

from sys import argv
from os.path import join
from batch_eval_top import eval_dir

FLAGS = tf.flags.FLAGS
tf.flags.DEFINE_integer("batch_size", "32", "batch size for training")
tf.flags.DEFINE_string("logs_dir", "../logs-vgg19_5channels_v3/", "path to logs directory")
tf.flags.DEFINE_string("data_dir", "../ISPRS_semantic_labeling_Vaihingen", "path to dataset")
tf.flags.DEFINE_float("learning_rate", "1e-4", "Learning rate for Adam Optimizer")
tf.flags.DEFINE_string("model_dir", "../pretrained_models/imagenet-vgg-verydeep-19.mat",
                       "Path to vgg model mat")
tf.flags.DEFINE_bool('debug', "False", "Debug mode: True/ False")
tf.flags.DEFINE_string('mode', "train", "Mode train/ test/ visualize")

MODEL_URL = 'http://www.vlfeat.org/matconvnet/models/beta16/imagenet-vgg-verydeep-19.mat'

# MAX_ITERATION = int(1e6 + 1)
MAX_ITERATION = int(121200 + 1) # 25 epochs with 16 top images
NUM_OF_CLASSES = 6
IMAGE_SIZE = 224
VALIDATE_IMAGES = ["top_mosaic_09cm_area7.png","top_mosaic_09cm_area17.png","top_mosaic_09cm_area23.png","top_mosaic_09cm_area37.png"]


def vgg_net(weights, image):
    layers = (
        'conv1_1', 'relu1_1', 'conv1_2', 'relu1_2', 'pool1',

        'conv2_1', 'relu2_1', 'conv2_2', 'relu2_2', 'pool2',

        'conv3_1', 'relu3_1', 'conv3_2', 'relu3_2', 'conv3_3',
        'relu3_3', 'conv3_4', 'relu3_4', 'pool3',

        'conv4_1', 'relu4_1', 'conv4_2', 'relu4_2', 'conv4_3',
        'relu4_3', 'conv4_4', 'relu4_4', 'pool4',

        'conv5_1', 'relu5_1', 'conv5_2', 'relu5_2', 'conv5_3',
        'relu5_3', 'conv5_4', 'relu5_4'
    )

    net = {}
    current = image
    for i, name in enumerate(layers):
        kind = name[:4]
        if kind == 'conv':
            kernels, bias = weights[i][0][0][0][0]
            # matconvnet: weights are [width, height, in_channels, out_channels]
            # tensorflow: weights are [height, width, in_channels, out_channels]
            if name == 'conv1_1':
                np.random.seed(3796)
                append_channels= np.random.normal(loc=0,scale=0.02,size=(3,3,2,64))
                # print(append_channels)
                kernels = np.concatenate((kernels, append_channels), axis=2)
                kernels = utils.get_variable(kernels, name=name + "_w")
            else:
                kernels = utils.get_variable(kernels, name=name + "_w")
            bias = utils.get_variable(bias.reshape(-1), name=name + "_b")
            current = utils.conv2d_basic(current, kernels, bias)
        elif kind == 'relu':
            current = tf.nn.relu(current, name=name)
            if FLAGS.debug:
                utils.add_activation_summary(current)
        elif kind == 'pool':
            current = utils.avg_pool_2x2(current)
        net[name] = current

    return net


def inference(image, keep_prob):
    """
    Semantic segmentation network definition
    :param image: input image. Should have values in range 0-255
    :param keep_prob:
    :return:
    """
    print("setting up vgg pretrained conv layers ...")
    model_data = utils.get_model_data(FLAGS.model_dir)

    mean = model_data['normalization'][0][0][0]
    mean_pixel = np.mean(mean, axis=(0, 1))
    mean_pixel = np.append(mean_pixel, [30.69861307993539, 284.9702])
    # mean_pixel = np.array([120.8952399852595, 81.93008162338278, 81.28988761879855, 30.69861307993539, 284.9702])
    weights = np.squeeze(model_data['layers'])

    processed_image = utils.process_image(image, mean_pixel)

    with tf.variable_scope("inference"):
        net = vgg_net(weights, processed_image)
        conv_final_layer = net["conv5_3"]

        pool5 = utils.max_pool_2x2(conv_final_layer)

        W6 = utils.weight_variable([7, 7, 512, 4096], name="W6")
        b6 = utils.bias_variable([4096], name="b6")
        conv6 = utils.conv2d_basic(pool5, W6, b6)
        relu6 = tf.nn.relu(conv6, name="relu6")
        if FLAGS.debug:
            utils.add_activation_summary(relu6)
        relu_dropout6 = tf.nn.dropout(relu6, keep_prob=keep_prob)

        W7 = utils.weight_variable([1, 1, 4096, 4096], name="W7")
        b7 = utils.bias_variable([4096], name="b7")
        conv7 = utils.conv2d_basic(relu_dropout6, W7, b7)
        relu7 = tf.nn.relu(conv7, name="relu7")
        if FLAGS.debug:
            utils.add_activation_summary(relu7)
        relu_dropout7 = tf.nn.dropout(relu7, keep_prob=keep_prob)

        W8 = utils.weight_variable([1, 1, 4096, NUM_OF_CLASSES], name="W8")
        b8 = utils.bias_variable([NUM_OF_CLASSES], name="b8")
        conv8 = utils.conv2d_basic(relu_dropout7, W8, b8)
        annotation_pred1 = tf.argmax(conv8, axis=3, name="prediction1")

        # now to upscale to actual image size
        deconv_shape1 = net["pool4"].get_shape()
        W_t1 = utils.weight_variable([4, 4, deconv_shape1[3].value, NUM_OF_CLASSES], name="W_t1")
        b_t1 = utils.bias_variable([deconv_shape1[3].value], name="b_t1")
        conv_t1 = utils.conv2d_transpose_strided(conv8, W_t1, b_t1, output_shape=tf.shape(net["pool4"]))
        fuse_1 = tf.add(conv_t1, net["pool4"], name="fuse_1")

        deconv_shape2 = net["pool3"].get_shape()
        W_t2 = utils.weight_variable([4, 4, deconv_shape2[3].value, deconv_shape1[3].value], name="W_t2")
        b_t2 = utils.bias_variable([deconv_shape2[3].value], name="b_t2")
        conv_t2 = utils.conv2d_transpose_strided(fuse_1, W_t2, b_t2, output_shape=tf.shape(net["pool3"]))
        fuse_2 = tf.add(conv_t2, net["pool3"], name="fuse_2")

        deconv_shape3 = net["pool2"].get_shape()
        W_t3 = utils.weight_variable([4, 4, deconv_shape3[3].value, deconv_shape2[3].value], name="W_t3")
        b_t3 = utils.bias_variable([deconv_shape3[3].value], name="b_t3")
        conv_t3 = utils.conv2d_transpose_strided(fuse_2, W_t3, b_t3, output_shape=tf.shape(net["pool2"]))
        fuse_3 = tf.add(conv_t3, net["pool2"], name="fuse_3")

        shape = tf.shape(image)
        deconv_shape4 = tf.stack([shape[0], shape[1], shape[2], NUM_OF_CLASSES])
        W_t4 = utils.weight_variable([8, 8, NUM_OF_CLASSES, deconv_shape3[3].value], name="W_t4")
        b_t4 = utils.bias_variable([NUM_OF_CLASSES], name="b_t4")
        conv_t4 = utils.conv2d_transpose_strided(fuse_3, W_t4, b_t4, output_shape=deconv_shape4, stride=4)

        annotation_pred = tf.argmax(conv_t4, axis=3, name="prediction")

    return tf.expand_dims(annotation_pred, dim=3), conv_t4


def train(loss_val, var_list):
    optimizer = tf.train.AdamOptimizer(FLAGS.learning_rate)
    grads = optimizer.compute_gradients(loss_val, var_list=var_list)
    if FLAGS.debug:
        # print(len(var_list))
        for grad, var in grads:
            utils.add_gradient_summary(grad, var)
    return optimizer.apply_gradients(grads)

def build_session(cuda_device):
    os.environ["CUDA_VISIBLE_DEVICES"] = cuda_device
    keep_probability = tf.placeholder(tf.float32, name="keep_probabilty")
    is_training = tf.placeholder(tf.bool, name="is_training")
    image = tf.placeholder(tf.float32, shape=[None, IMAGE_SIZE, IMAGE_SIZE, 5], name="input_image")
    annotation = tf.placeholder(tf.int32, shape=[None, IMAGE_SIZE, IMAGE_SIZE, 1], name="annotation")
    pred_annotation, logits = inference(image, keep_probability)
    annotation_64 = tf.cast(annotation, dtype=tf.int64)
    # calculate accuracy for batch.
    cal_acc = tf.equal(pred_annotation, annotation_64)
    cal_acc = tf.cast(cal_acc, dtype=tf.int8)
    acc = tf.count_nonzero(cal_acc) / (FLAGS.batch_size * IMAGE_SIZE * IMAGE_SIZE)
    tf.summary.image("input_image", image, max_outputs=2)
    tf.summary.image("ground_truth", tf.cast(annotation, tf.uint8), max_outputs=2)
    tf.summary.image("pred_annotation", tf.cast(pred_annotation, tf.uint8), max_outputs=2)
    loss = tf.reduce_mean((tf.nn.sparse_softmax_cross_entropy_with_logits(logits=logits,
                                                                          labels=tf.squeeze(annotation,
                                                                                            squeeze_dims=[3]),
                                                                          name="entropy")))
    loss_summary = tf.summary.scalar("entropy", loss)
    # summary accuracy in tensorboard
    acc_summary = tf.summary.scalar("accuracy", acc)
    trainable_var = tf.trainable_variables()
    if FLAGS.debug:
        for var in trainable_var:
            utils.add_to_regularization_and_summary(var)
    train_op = train(loss, trainable_var)
    print("Setting up summary op...")
    summary_op = tf.summary.merge_all()

    sess = tf.Session()

    print("Setting up Saver...")
    saver = tf.train.Saver()
    train_writer = tf.summary.FileWriter(FLAGS.logs_dir + '/train', sess.graph)
    validation_writer = tf.summary.FileWriter(FLAGS.logs_dir + '/validation')
    sess.run(tf.global_variables_initializer())
    ckpt = tf.train.get_checkpoint_state(FLAGS.logs_dir)
    if ckpt and ckpt.model_checkpoint_path:
        saver.restore(sess, ckpt.model_checkpoint_path)
        print("Model restored...")
    return image, logits, keep_probability, sess, annotation, train_op, loss, acc, loss_summary, acc_summary, saver, pred_annotation, train_writer, validation_writer, is_training

def main(argv=None):
    image, logits, keep_probability, sess, annotation, train_op, loss, acc, loss_summary, acc_summary, saver, pred_annotation, train_writer, validation_writer, is_training = build_session(argv[1])

    print("Setting up image reader...")
    train_records, valid_records = reader.read_dataset(FLAGS.data_dir)
    print(len(train_records))
    print(len(valid_records))

    print("Setting up dataset reader")
    image_options = {'resize': False, 'resize_size': IMAGE_SIZE}
    if FLAGS.mode == 'train':
        train_dataset_reader = dataset.Batch_manager(train_records, image_options)
    # Comment if Submission only
    validation_dataset_reader = dataset.Batch_manager(valid_records, image_options)
    
    """ os.environ["CUDA_VISIBLE_DEVICES"] = argv[1]
    keep_probability = tf.placeholder(tf.float32, name="keep_probabilty")
    image = tf.placeholder(tf.float32, shape=[None, IMAGE_SIZE, IMAGE_SIZE, 5], name="input_image")
    annotation = tf.placeholder(tf.int32, shape=[None, IMAGE_SIZE, IMAGE_SIZE, 1], name="annotation")
    pred_annotation, logits = inference(image, keep_probability)
    annotation_64 = tf.cast(annotation, dtype=tf.int64)
    # calculate accuracy for batch.
    cal_acc = tf.equal(pred_annotation, annotation_64)
    cal_acc = tf.cast(cal_acc, dtype=tf.int8)
    acc = tf.count_nonzero(cal_acc) / (FLAGS.batch_size * IMAGE_SIZE * IMAGE_SIZE)
    tf.summary.image("input_image", image, max_outputs=2)
    tf.summary.image("ground_truth", tf.cast(annotation, tf.uint8), max_outputs=2)
    tf.summary.image("pred_annotation", tf.cast(pred_annotation, tf.uint8), max_outputs=2)
    loss = tf.reduce_mean((tf.nn.sparse_softmax_cross_entropy_with_logits(logits=logits,
                                                                          labels=tf.squeeze(annotation,
                                                                                            squeeze_dims=[3]),
                                                                          name="entropy")))
    loss_summary=tf.summary.scalar("entropy", loss)
    # summary accuracy in tensorboard
    acc_summary=tf.summary.scalar("accuracy", acc)
    trainable_var = tf.trainable_variables()
    if FLAGS.debug:
        for var in trainable_var:
            utils.add_to_regularization_and_summary(var)
    train_op = train(loss, trainable_var)
    print("Setting up summary op...")
    summary_op = tf.summary.merge_all()

    config = tf.ConfigProto()
    config.gpu_options.allow_growth = True
    sess = tf.Session(config=config)

    print("Setting up Saver...")
    saver = tf.train.Saver()
    train_writer = tf.summary.FileWriter(FLAGS.logs_dir + '/train', sess.graph)
    validation_writer = tf.summary.FileWriter(FLAGS.logs_dir + '/validation')
    sess.run(tf.global_variables_initializer())
    ckpt = tf.train.get_checkpoint_state(FLAGS.logs_dir)
    if ckpt and ckpt.model_checkpoint_path:
        saver.restore(sess, ckpt.model_checkpoint_path)
        print("Model restored...") """
    
    if FLAGS.mode == "train":
        for itr in xrange(MAX_ITERATION):
            train_images, train_annotations = train_dataset_reader.next_batch(saver, FLAGS.batch_size, image, logits, keep_probability, sess, is_training, FLAGS.logs_dir)
            feed_dict = {image: train_images, annotation: train_annotations, keep_probability: 0.5, is_training: True}
            sess.run(train_op, feed_dict=feed_dict)

            if itr % 50 == 0:
                train_loss, train_acc, summary_loss, summary_acc = sess.run([loss, acc, loss_summary, acc_summary], feed_dict=feed_dict)
                print("Step: %d, Train_loss: %g, Train_acc: %g" % (itr, train_loss, train_acc))
                with open(join(FLAGS.logs_dir, 'iter_train_loss.csv'), 'a') as f:
                    f.write(str(itr) + ',' + str(train_loss) + '\n')
                with open(join(FLAGS.logs_dir, 'iter_train_acc.csv'), 'a') as f:
                    f.write(str(itr) + ',' + str(train_acc) + '\n')
                train_writer.add_summary(summary_loss, itr)
                train_writer.add_summary(summary_acc, itr)
            if itr % 600 == 0:
                valid_images, valid_annotations = validation_dataset_reader.next_batch(saver, FLAGS.batch_size, image, logits, keep_probability, sess, is_training, FLAGS.logs_dir, is_validation=True)
                valid_loss, valid_acc, summary_loss, summary_acc = sess.run([loss, acc, loss_summary, acc_summary], feed_dict={image: valid_images, annotation: valid_annotations, keep_probability: 1.0, is_training: False})
                validation_writer.add_summary(summary_loss, itr)
                validation_writer.add_summary(summary_acc, itr)
                print("%s ---> Validation_loss: %g , Validation Accuracy: %g" % (datetime.datetime.now(), valid_loss, valid_acc))
                with open(join(FLAGS.logs_dir, 'iter_val_loss.csv'), 'a') as f:
                    f.write(str(itr) + ',' + str(valid_loss) + '\n')
                with open(join(FLAGS.logs_dir, 'iter_val_acc.csv'), 'a') as f:
                    f.write(str(itr) + ',' + str(valid_acc) + '\n')
                # saver.save(sess, FLAGS.logs_dir + "model.ckpt", itr)
    elif FLAGS.mode == "visualize":
        valid_images, valid_annotations = validation_dataset_reader.get_random_batch(FLAGS.batch_size)
        pred = sess.run(pred_annotation, feed_dict={image: valid_images, annotation: valid_annotations,
                                                    keep_probability: 1.0})
        valid_annotations = np.squeeze(valid_annotations, axis=3)
        pred = np.squeeze(pred, axis=3)

        for itr in range(FLAGS.batch_size):
            print(valid_images[itr].astype(np.uint8).shape)
            utils.save_image(valid_images[itr, :, :, :3].astype(np.uint8), FLAGS.logs_dir, name="inp_" + str(itr))
            print(valid_annotations[itr].astype(np.uint8).shape)
            utils.save_image(valid_annotations[itr].astype(np.uint8), FLAGS.logs_dir, name="gt_" + str(itr))
            print(pred[itr].astype(np.uint8).shape)
            utils.save_image(pred[itr].astype(np.uint8), FLAGS.logs_dir, name="pred_" + str(itr))
            print("Saved image: %d" % itr)

if __name__ == "__main__":
    tf.app.run()