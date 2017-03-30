# pyusbee
Python tool interfacing the USBEE DX pod on Windows

This tool captures the data from the USB DX pod and stores it into a VCD file that can be specified at the command line.

If the VCD file is not specified, it will create a shared memory to write the vcd data in a format that can be read out by GTKWave.  This allows viewing the USBEE DX data into the waveform viewer without any limit in time.

Furthermore the tool has an interactive command line interface to allow interacting with the pod: start, stop, create trigger options etc...

