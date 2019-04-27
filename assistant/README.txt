First thing we need to do is install all the requirments to do that enter the following command
pip install -r requirments.txt 

Make sure you the .cfg file for ibm cloud and the client_secret file to connect to ibm iot and google assistant api

Make sure to change the file name to your .cfg file

You'll also need to change the project name and device name when calling the main method to your
respective ones.

The file jay_randy.pickle is the model that is used to recognized the faces. This model can be built using build_model.py file in build_model folder

The .xml file is a cascade file required for front facial detection

To run the code all  you need to do is type
pyton assistant.py

The folder assistant-sdk-python contains the google assistant sdk
