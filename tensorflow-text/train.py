#! /usr/bin/env python

import tensorflow as tf
import numpy as np
import os
import time
import datetime
import data_helpers.load as load_utils
import data_helpers.vocab as vocab_utils
from tf_helpers.models import naive_rnn, attention_rnn, text_cnn
from tensorflow.contrib import learn

# Parameters
# ==================================================

# Data loading params
tf.flags.DEFINE_float("dev_sample_percentage", .1, "Percentage of the training data to use for validation")
tf.flags.DEFINE_string("data", "../data/dataset/sample_data/train.tsv", "Data source for training and validation set")
#tf.flags.DEFINE_string("positive_data_file", "./data/rt-polaritydata/rt-polarity.pos", "Data source for the positive data.")
#tf.flags.DEFINE_string("negative_data_file", "./data/rt-polaritydata/rt-polarity.neg", "Data source for the negative data.")

# Network type
tf.flags.DEFINE_string("model", "blstm", "Network model to train: blstm | blstm_att | cnn (default: blstm)")

# Model directory
tf.flags.DEFINE_string("output_dir", "", "Where to save the trained model, checkpoints and stats (default: current_dir/runs/timestamp)")

# Model Hyperparameters
tf.flags.DEFINE_integer("embedding_dim", 300, "Dimensionality of character embedding. (for cnn: use 128). (default: 300)")
tf.flags.DEFINE_string("filter_sizes", "3,4,5", "Comma-separated filter sizes (default: '3,4,5')")
tf.flags.DEFINE_integer("num_filters", 128, "Number of filters per filter size (default: 128)")
tf.flags.DEFINE_integer("num_cells", 100, "Number of cells in each BLSTM layer (default: 100)")
tf.flags.DEFINE_integer("num_layers", 2, "Number of BLSTM layers (default: 2)")
tf.flags.DEFINE_float("learning_rate", 1e-3, "Learning rate for backpropagation (default: 1e-3)")
tf.flags.DEFINE_string("glove_embedding", "", "Path to a file containing Glove pretrained vectors (default: None)")
tf.flags.DEFINE_string("fasttext_embedding", "", "Path to a file containing Fasttext pretrained vectors (default: None)")
tf.flags.DEFINE_float("dropout_keep_prob", 0.75, "Dropout keep probability (default: 0.75)")
tf.flags.DEFINE_float("l2_reg_lambda", 0.0, "L2 regularization lambda (default: 0.0)")

# Training parameters
tf.flags.DEFINE_integer("batch_size", 64, "Batch Size (default: 64)")
tf.flags.DEFINE_integer("num_epochs", 10, "Number of training epochs (default: 10)")
tf.flags.DEFINE_integer("evaluate_every", 2000, "Evaluate model on dev set after this many steps (default: 2000)")
tf.flags.DEFINE_integer("checkpoint_every", 2000, "Save model after this many steps (default: 2000)")
tf.flags.DEFINE_integer("num_checkpoints", 25, "Max number of checkpoints to store (default: 25)")
# Misc Parameters
tf.flags.DEFINE_boolean("allow_soft_placement", True, "Allow device soft device placement")
tf.flags.DEFINE_boolean("log_device_placement", False, "Log placement of ops on devices")

FLAGS = tf.flags.FLAGS
# FLAGS._parse_flags()
# print("\nParameters:")
# for attr, value in sorted(FLAGS.__flags.items()):
#     print("{}={}".format(attr.upper(), value))
# print("")

if not FLAGS.output_dir:
    timestamp = str(int(time.time()))
    FLAGS.output_dir = os.path.abspath(os.path.join(os.path.curdir, "runs", timestamp))

if not os.path.exists(FLAGS.output_dir):
    os.makedirs(FLAGS.output_dir)


def preprocess():
    # Data Preparation
    # ==================================================

    # Load data
    print("Loading data...")
    x_text, y = load_utils.load_data_and_labels(FLAGS.data)

    # Build vocabulary
    max_element_length = max([len(x.split(" ")) for x in x_text])

    word_dict, reversed_dict = load_utils.build_dict(x_text, os.path.join(FLAGS.output_dir, "vocab") )
    
    x = load_utils.transform_text(x_text, word_dict, max_element_length)
    x = np.array(x)

    # Randomly shuffle data
    np.random.seed(10)
    shuffle_indices = np.random.permutation(np.arange(len(y)))
    x_shuffled = x[shuffle_indices]
    y_shuffled = y[shuffle_indices]

    # Split train/test set
    # TODO: This is very crude, should use cross-validation
    dev_sample_index = -1 * int(FLAGS.dev_sample_percentage * float(len(y)))
    x_train, x_valid = x_shuffled[:dev_sample_index], x_shuffled[dev_sample_index:]
    y_train, y_valid = y_shuffled[:dev_sample_index], y_shuffled[dev_sample_index:]

    del x, y, x_shuffled, y_shuffled

    print("Vocabulary Size: {:d}".format(len(word_dict)))
    print("Train/Dev split: {:d}/{:d}".format(len(y_train), len(y_valid)))
    
    return x_train, y_train, word_dict, reversed_dict, x_valid, y_valid





def train(x_train, y_train, word_dict, reversed_dict, x_valid, y_valid):
    # Training
    # ==================================================

    with tf.Graph().as_default():
        session_conf = tf.ConfigProto(
          allow_soft_placement=FLAGS.allow_soft_placement,
          log_device_placement=FLAGS.log_device_placement)
        sess = tf.Session(config=session_conf)
        with sess.as_default():

            if (FLAGS.model == "blstm"):
                model = naive_rnn.NaiveRNN(
                    reversed_dict=reversed_dict,
                    sequence_length=x_train.shape[1],
                    num_classes=y_train.shape[1],
                    embedding_size=FLAGS.embedding_dim,
                    num_cells=FLAGS.num_cells,
                    num_layers=FLAGS.num_layers,
                    glove_embedding=FLAGS.glove_embedding,
                    fasttext_embedding=FLAGS.fasttext_embedding,
                    learning_rate=FLAGS.learning_rate)
            elif (FLAGS.model == "blstm_att"):
                model = attention_rnn.AttentionRNN(
                    reversed_dict=reversed_dict,
                    sequence_length=x_train.shape[1],
                    num_classes=y_train.shape[1],
                    embedding_size=FLAGS.embedding_dim,
                    num_cells=FLAGS.num_cells,
                    num_layers=FLAGS.num_layers,
                    glove_embedding=FLAGS.glove_embedding,
                    fasttext_embedding=FLAGS.fasttext_embedding,
                    learning_rate=FLAGS.learning_rate)
            elif (FLAGS.model == "cnn"):
                model = text_cnn.TextCNN(
                    reversed_dict = reversed_dict,
                    sequence_length=x_train.shape[1],
                    num_classes=y_train.shape[1],
                    embedding_size=FLAGS.embedding_dim,
                    filter_sizes=list(map(int, FLAGS.filter_sizes.split(","))),
                    num_filters=FLAGS.num_filters,
                    learning_rate=FLAGS.learning_rate,
                    l2_reg_lambda=FLAGS.l2_reg_lambda)
            else:
                raise NotImplementedError()


            # Keep track of gradient values and sparsity (optional)
            grad_summaries = []
            for g, v in model.grads_and_vars:
                if g is not None:
                    grad_hist_summary = tf.summary.histogram("{}/grad/hist".format(v.name), g)
                    sparsity_summary = tf.summary.scalar("{}/grad/sparsity".format(v.name), tf.nn.zero_fraction(g))
                    grad_summaries.append(grad_hist_summary)
                    grad_summaries.append(sparsity_summary)
            grad_summaries_merged = tf.summary.merge(grad_summaries)
            
            # Output directory for models and summaries

            print("Writing to {}\n".format(FLAGS.output_dir))

            # Summaries for loss and accuracy
            loss_summary = tf.summary.scalar("loss", model.loss)
            acc_summary = tf.summary.scalar("accuracy", model.accuracy)

            # Train Summaries
            train_summary_op = tf.summary.merge([loss_summary, acc_summary, grad_summaries_merged])
            train_summary_dir = os.path.join(FLAGS.output_dir, "summaries", "train")
            train_summary_writer = tf.summary.FileWriter(train_summary_dir, sess.graph)

            # Dev summaries
            dev_summary_op = tf.summary.merge([loss_summary, acc_summary])
            dev_summary_dir = os.path.join(FLAGS.output_dir, "summaries", "dev")
            dev_summary_writer = tf.summary.FileWriter(dev_summary_dir, sess.graph)

            # Checkpoint directory. Tensorflow assumes this directory already exists so we need to create it
            checkpoint_dir = os.path.abspath(os.path.join(FLAGS.output_dir, "checkpoints"))
            checkpoint_prefix = os.path.join(checkpoint_dir, "model")
            if not os.path.exists(checkpoint_dir):
                os.makedirs(checkpoint_dir)
            saver = tf.train.Saver(tf.global_variables(), max_to_keep=FLAGS.num_checkpoints)

            # Initialize all variables
            sess.run(tf.global_variables_initializer())

            def train_step(x_train_batch, y_train_batch):
                """
                A single training step
                """
                feed_dict = {
                  model.input_x: x_train_batch,
                  model.input_y: y_train_batch,
                  model.dropout_keep_prob: FLAGS.dropout_keep_prob
                }

                _, step, summaries, loss, accuracy = sess.run(
                    [model.optimizer, model.global_step, train_summary_op, model.loss, model.accuracy],feed_dict)

                time_str = datetime.datetime.now().isoformat()
                print("{}: step {}, loss {:g}, acc {:g}".format(time_str, step, loss, accuracy))
                train_summary_writer.add_summary(summaries, step)

                return accuracy


            def dev_step(x_valid, y_valid, writer=None):
                """
                Evaluates model on the full validation set
                """

                valid_batches = load_utils.batch_iter(list(zip(x_valid, y_valid)), FLAGS.batch_size, 1)

                sum_accuracy, cnt = 0, 0
                for valid_batch in valid_batches:
                    x_valid_batch, y_valid_batch = zip(*valid_batch)

                    feed_dict = {
                        model.input_x: x_valid_batch,
                        model.input_y: y_valid_batch,
                        model.dropout_keep_prob: 1.0
                    }

                    step, summaries, loss, accuracy = sess.run(
                        [model.global_step, dev_summary_op, model.loss, model.accuracy], feed_dict)

                    sum_accuracy += accuracy
                    cnt += 1

                if writer:
                    writer.add_summary(summaries, step)

                valid_accuracy = sum_accuracy / cnt

                return valid_accuracy

            # Generate batches
            train_batches = load_utils.batch_iter(list(zip(x_train, y_train)), FLAGS.batch_size, FLAGS.num_epochs)
            num_batches_per_epoch = (len(x_train) - 1) // FLAGS.batch_size + 1

            max_accuracy = 0
            # Training loop. For each batch...
            for train_batch in train_batches:
                x_train_batch, y_train_batch = zip(*train_batch)
                train_step(x_train_batch, y_train_batch)
                current_step = tf.train.global_step(sess, model.global_step)
                if current_step % FLAGS.evaluate_every == 0:
                    print("\nEvaluation:")
                    valid_accuracy = dev_step(x_valid, y_valid, writer=None)

                    time_str = datetime.datetime.now().isoformat()
                    print("{}: step {}, valid_accuracy {:g}".format(time_str, current_step, valid_accuracy))
                
                    if valid_accuracy > max_accuracy:
                        max_accuracy = valid_accuracy
                        path = saver.save(sess, checkpoint_prefix, global_step=current_step)
                        print("Saved model with better accuracy to {}\n".format(path))
                        continue

                if current_step % FLAGS.checkpoint_every == 0:
                    path = saver.save(sess, checkpoint_prefix, global_step=current_step)
                    print("Saved model checkpoint to {}\n".format(path))





def main(argv=None):
    x_train, y_train, word_dict, reversed_dict, x_valid, y_valid = preprocess()
    train(x_train, y_train, word_dict, reversed_dict, x_valid, y_valid)

if __name__ == '__main__':
    tf.app.run()