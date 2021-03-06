from flask import Flask, render_template, session, request, Response, redirect, url_for
import os
import sys
import base64
import urllib
import re
from functools import wraps

from PIL import Image
import cStringIO
import numpy as np
from scipy.misc import imread, imsave, imresize
import tensorflow as tf

sys.path.insert(0, './enhance')
import sres


sres.NUM_FILTERS = 64
sres.FIRST_FILTER_SIZE = 3
sres.SECOND_FILTER_SIZE = 3
sres.THIRD_FILTER_SIZE = 3

input_images = tf.placeholder(tf.float32, shape=[1, 2, 90, 120, 3])
output_images = sres.generator(input_images)

tf.get_variable_scope().reuse_variables()
saver = tf.train.Saver() 

sess = tf.Session()

saver.restore(sess, 'model/best_model.ckpt-39999')


app = Flask(__name__)


def predict_and_save(data, filename, shape=None):

    generated_images = sess.run(output_images, feed_dict={input_images: data})
    current_frame = generated_images[0, 1]

    if shape:
        current_frame = imresize(current_frame, shape)

    imsave(filename, current_frame)


def process_frames(previous_frame, current_frame, shape=(90, 120, 3)):

    if os.path.exists(previous_frame):
        previous_image = imread(previous_frame)
    else:
        previous_image = np.ones(shape)

    if os.path.exists(current_frame):
        current_image = imread(current_frame)
    else:
        current_image = np.ones(shape)

    images = np.stack([[previous_image, current_image]])
    images = images / 127.5 - 1.0

    return images


def check_auth(username, password):
    """This function is called to check if a username /
    password combination is valid.
    """
    return username == 'admin' and password == 'secret'


def authenticate():
    """Sends a 401 response that enables basic auth"""
    return Response(
    'Could not verify your access level for that URL.\n'
    'You have to login with proper credentials', 401,
    {'WWW-Authenticate': 'Basic realm="Login Required"'})


def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated


@app.route('/webcam', methods=['GET', 'POST'])
@requires_auth
def webcam():
    """Video streaming home page."""
    if request.method == 'GET':

        return render_template('webcam.html')

    if request.method == 'POST':
        
        image_b64 = request.form['frame_data']
        image_data = re.sub('^data:image/.+;base64,', '', image_b64)
        image_data = image_data.decode('base64')

        if os.path.exists('static/current_frame.jpg'):
            os.rename('static/current_frame.jpg', 'static/previous_frame.jpg')

        with open('static/current_frame.jpg', 'w') as f:
            f.write(image_data)

        input_images = process_frames('static/previous_frame.jpg', 'static/current_frame.jpg')
        predict_and_save(input_images, 'static/upsampled_frame.jpg')

        resized_image = imresize(input_images[0, 1], 400, interp='bicubic')
        imsave('static/interp_frame.jpg', resized_image)

        return ''


@app.route('/')
def index():
    """Video streaming home page."""
    return render_template('index.html')


if __name__ == '__main__':

    app.run(debug=True)
