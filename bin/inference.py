#!/usr/bin/env python

# TensorFlow and tf.keras
import os
# 0 = all messages are logged (default behavior)
# 1 = INFO messages are not printed
# 2 = INFO and WARNING messages are not printed
# 3 = INFO, WARNING, and ERROR messages are not printed
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '1'

import sys
import time
import argparse

from src.utils.logger import Logging
from src.utils.color_utils import bcolors
Logging.attach_stdout()
#HuliLogging.debug_dim()
#HuliLogging.info_blue()
#HuliLogging.warn_yellow()
#HuliLogging.error_red()
logger = Logging.get_logger(__name__)


from src.meta.tensor_apis import TensorApi
from bin.train import get_data, get_model, MODEL_NAMES

import tensorflow as tf



logger.info('=' * 50)
logger.info('tensorflow-%s' % tf.__version__)
logger.info('=' * 50)

DEFAULT_WARM_UP = 25
DEFAULT_TRIALS = 100
DEFAULT_REPEAT = 3

DEFAULT_KERAS_INFERENCE = True
DEFAULT_TENSORFLOW_INFERENCE = True
DEFAULT_TFLITE_INFERENCE = True
DEFAULT_TRT_INFERENCE = False


epoch = 0

def line():
    return '=' * 50


def log_prefix():
    global epoch
    return '[%s|%d]' % ('train', epoch)


def log_bold(*argv, **kwargs):
    logger.info(log_prefix() + ' ' + line() + ' ' + argv[0] + ' ' + line(), *argv[1:], **kwargs)


def get_time_format(num):
    return '%3d' if num >= 100 else '%2d' if num >= 10 else '%d'


def predict(model, test_images, trials, log_first=0, log_last=0):
    start = time.time()
    longest_line = 0
    for i in range(0, trials):
        now = time.time()
        ret, y = model.predict(test_images)
        if ret != 0:
            logger.error('Failed predicting with error %d', ret)
            return ret, None
        elapsed = time.time() - now
        running_avg = (time.time() - start) / (i + 1)

        time_format = get_time_format(trials)
        log = (time_format + ': %.3fs') % (i + 1, elapsed)
        if i < log_first or i > trials - log_last:
            print(log)
        else:
            if i + 1 != trials:
                log += ' ['
                log += '=' * i
                log += '>'
                log += '.' * (trials - i - 1)
                log += ']'
                remaining_time = running_avg * (trials - i - 1)
                log += ' ETA: %.3fs' % remaining_time
            longest_line = max(len(log), longest_line)
            if len(log) < longest_line:
                log += ' ' * (longest_line - len(log))
            print('\r%s' % log, end='\r')

        yield 0, elapsed


def warm_up(model, test_images, trials, time_format):
    logger.info('%s Warming up on %d images for %d iterations...' % (model.name, len(test_images), trials))
    timings = []
    for ret, p in predict(model, test_images, trials):
        if ret != 0:
            return ret
        timings.append(p)
    elapsed = sum(timings)
    log_images_size = ('%d' % len(test_images)).ljust(5)
    log_prefix_ = ('%s [' + time_format + 'x%s %s]') % (log_prefix(), len(timings), log_images_size, model.mode)
    logger.info('%s Warm up =   %.3fs (avg = %.3fs)' % (log_prefix_, elapsed, elapsed / len(timings)))

    return 0


def test(model, test_images, trials, repeat, time_format):
    if len(test_images) == 1:
        phrase = 'single image'
    else:
        phrase = 'batch of %d images' % len(test_images)
    logger.info('%s %s Repeat %dx timing on %s for %d iterations...', log_prefix(), model.name, repeat, phrase, trials)
    for i in range(repeat):
        timings = []
        for ret, p in predict(model, test_images, trials):
            if ret != 0:
                return ret
            timings.append(p)
        elapsed = sum(timings)
        log_images_size = ('%d' % len(test_images)).ljust(5)
        log_prefix_ = ('%s [' + time_format + 'x%s %s]') % (log_prefix(), len(timings), log_images_size, model.mode)
        logger.info('%s Test time = %.3fs (avg = %.3fs)' % (log_prefix_, elapsed, elapsed / len(timings)))

    return 0


def infer(model, test_images, do_keras=DEFAULT_KERAS_INFERENCE, do_tensorflow=DEFAULT_TENSORFLOW_INFERENCE,
          do_tflite=DEFAULT_TFLITE_INFERENCE, do_trt=DEFAULT_TRT_INFERENCE, warm_up_trials=DEFAULT_WARM_UP,
          trials=DEFAULT_TRIALS, repeat=DEFAULT_REPEAT):
    time_format = get_time_format(len(test_images))

    # Test multiple sizes
    for i in [1, 10, 100, 1000]:
        def run(mode):
            ret = model.change_mode(mode)
            if ret != 0:
                logger.error('%s Changing to mode %s failed with error %d', log_prefix(), TensorApi.KERAS, ret)
                exit(1)
            log_bold('WARM UP')
            ret = warm_up(model, test_images[:i], warm_up_trials, time_format)
            if ret != 0:
                return ret
            log_bold('TEST')
            ret = test(model, test_images[:i], trials, repeat, time_format)
            if ret != 0:
                return ret

        if do_keras:
            log_bold(str(TensorApi.KERAS))
            run(TensorApi.KERAS)
        if do_tensorflow:
            log_bold(str(TensorApi.TENSORFLOW))
            run(TensorApi.TENSORFLOW)
        if do_tflite:
            log_bold(str(TensorApi.TF_LITE))
            run(TensorApi.TF_LITE)
        if do_trt:
            log_bold(str(TensorApi.TENSOR_RT))
            run(TensorApi.TENSOR_RT)

    return 0


def get_args():
    p = argparse.ArgumentParser()
    p.add_argument('-e', '--epoch', type=int, default=1, help='Training epoch.')
    p.add_argument('-m', '--model', required=True, help='Model name. One of %s' % MODEL_NAMES)
    p.add_argument('-w', '--warm-up', type=int, default=DEFAULT_WARM_UP, help='Warmup trials')
    p.add_argument('-t', '--trials', type=int, default=DEFAULT_TRIALS, help='Test trials')
    p.add_argument('-r', '--repeat', type=int, default=DEFAULT_REPEAT, help='Repeat sceneratios')
    p.add_argument('--skip-keras', default=not DEFAULT_KERAS_INFERENCE, help='Skip keras inference',
                   action="store_true")
    p.add_argument('--skip-tensorflow', default=not DEFAULT_TENSORFLOW_INFERENCE, help='Skip tensorflow inference',
                   action="store_true")
    p.add_argument('--skip-tflite', default=not DEFAULT_TFLITE_INFERENCE, help='Skip tflite inference',
                   action="store_true")
    p.add_argument('--skip-trt', default=not DEFAULT_TRT_INFERENCE, help='Skip trt inference', action="store_true")
    args, unknown = p.parse_known_args()
    assert args.model in MODEL_NAMES
    assert args.epoch > 0
    assert args.warm_up >= 0
    assert args.trials >= 1
    assert args.repeat >= 1
    return args


def main():
    # Args
    log_bold('PARSE')
    args = get_args()
    model_name = args.model
    global epoch
    epoch = args.epoch
    warm_up_trials = args.warm_up
    trials = args.trials
    repeat = args.repeat

    # Load Data
    log_bold('DATA')
    (train_images, train_labels), (test_images, test_labels) = get_data()

    # Load Model
    log_bold('MODEL')
    ret, model = get_model(model_name, epoch)
    if ret != 0:
        logger.error('%s Getting model failed with error %d', log_prefix(), ret)
        exit(1)
    model.summary()

    log_bold('INFER')
    ret = infer(model, test_images, do_keras=not args.skip_keras, do_tensorflow=not args.skip_tensorflow,
                do_tflite=not args.skip_tflite, do_trt=not args.skip_trt, warm_up_trials=warm_up_trials, trials=trials,
                repeat=repeat)
    if ret != 0:
        logger.error('%s Failed infer with error %d', log_prefix(), ret)
        return ret

    return 0


if __name__ == '__main__':
    now = time.time()
    logger.info('')
    logger.info('')
    bcolors.light_cyan(logger.info, '> ' + ' '.join(sys.argv))

    ret = 0
    try:
        main()
    except Exception as e:
        logger.exception('Uncaught exception: %s', e)
        ret = 1
    logger.info('')
    bcolors.light_cyan(logger.info, '> ' + ' '.join(sys.argv))
    logger.info('')

    if ret == 0:
        bcolors.light_green(logger.info, '[%.3fs] SUCCESS!!!', time.time() - now)
    else:
        bcolors.light_red(logger.error, '[%.3fs] FAIL!!!', time.time() - now)

    exit(ret)
