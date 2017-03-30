# pyusbee
Python tool interfacing the USBEE DX pod on Windows

# prerequisites
Python for windows must be installed:  the 32 bit version is mandatory, otherwise the DLL can not be loaded correctly
The USBEE drivers must be installed.  I have copied all the installation files in the appropriate directory, I do not know which one exactly is necessary.

# description 
This tool captures the data from the USB DX pod and stores it into a VCD file that can be specified at the command line.

If the VCD file is not specified, it will create a shared memory to write the vcd data in a format that can be read out by GTKWave.  This allows viewing the USBEE DX data into the waveform viewer without any limit in time.

Furthermore the tool has an interactive command line interface to allow interacting with the pod: start, stop, create trigger options etc...

# how to start it
I usually start it from the cygwin command line (for command completion etc..) but it can easily be done from the windows command shell.

To start a capture in a file:
/cygdrive/c/Python27/python pyusbee.py 5452 capture.vcd

To start a capture in SHM for use with GTKWave:
/cygdrive/c/Python27/python pyusbee.py 5452

and to launch GTKWave in another terminal to display the content of the shared memory:
<path_to_gtkwave_bin>/gtkwave -I 5452