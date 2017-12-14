import argparse
import cmd
import ctypes
import time
import threading
import Queue
import textwrap
import mmap

try:
    # Load DLL into memory.
    usbedBasicDll = ctypes.WinDLL(".\\usbedBasic.dll")
except:
    print("there are many sources of errors when loading DLLs:")
    print("  - check the presence of the DLL")
    print("  - check the python interpreter , IT MUST BE BUILT for x86, not x86-64")
    raise

#StartExtraction  Starts the Data Extraction with the given parameters.
#CWAV_EXPORT int CWAV_API StartExtraction( unsigned int SampleRate, unsigned long PodNumber, unsigned int ClockMode);
#SampleRate:
# 17 = 1Msps
# 27 = 2Msps
# 37 = 3Msps
# 47 = 4Msps
# 67 = 6Msps
# 87 = 8Msps
# 127 = 12Msps
# 167 = 16Msps
# 247 = 24Msps
#PodNumber: Pod ID on the back of the USBee DX Test Pod
#ClockMode:
# 2 : Internal Timing as in SampleRate parameter
# 4 : External Timing : sample on rising edge of CLK
# 5 : External Timing : sample on falling edge of CLK
# 6 : External Timing : sample on rising edge of CLK and TRG high
# 7 : External Timing : sample on falling edge of CLK and TRG high
# 8 : External Timing : sample on rising edge of CLK and TRG low
# 9 : External Timing : sample on falling edge of CLK and TRG low
#Returns:
# 1 : if Start was successful
# 0 : if Pod failed initialization

#StopExtraction  Stops the extraction in progress
#CWAV_EXPORT int CWAV_API StopExtraction( void );
#Returns:
# 1 : always

#ExtractBufferOverflow " Returns the state of the overflow conditions
#CWAV_EXPORT char CWAV_API ExtractBufferOverflow(void);
#Return:
# 0 : No overflow
# 1 : Overflow Occurred. ExtractorBuffer Overflow condition cleared.
# 2 : Overflow Occurred. Raw Stream Buffer Overflow

#ExtractionBufferCount  Returns the number of bytes that have been extracted from the data stream
#so far and are available to read using GetNextData.
#CWAV_EXPORT unsigned long CWAV_API ExtractionBufferCount(void)
#Returns:
# 0 : No data to read yet
# other : number of bytes available to read

#GetNextData  Copies the extracted data from the extractor into your working buffer
#CWAV_EXPORT char CWAV_API GetNextData(unsigned char *buffer,
#unsigned long length);
#buffer: pointer to where you want the extracted data to be placed
#length: number of bytes you want to read from the extraction DLL
#Returns:
# 0 : No data to read yet
# 1 : Data was copied into the buffer



# Set up prototype and parameters for the desired function call.

#ctypes.WINFUNCTYPE(restype, *argtypes, use_errno=False, use_last_error=False)
StartExtractionProto = ctypes.WINFUNCTYPE (
    ctypes.c_int,      # Return type.
    ctypes.c_uint,     # samplerate
    ctypes.c_ulong,    # pod number
    ctypes.c_uint)     # clockmode.

StopExtractionProto = ctypes.WINFUNCTYPE (
    ctypes.c_int)      # Return type.

ExtractBufferOverflowProto = ctypes.WINFUNCTYPE (
    ctypes.c_char)      # Return type.

ExtractionBufferCountProto = ctypes.WINFUNCTYPE (
    ctypes.c_ulong)      # Return type.

GetNextDataProto = ctypes.WINFUNCTYPE (
    ctypes.c_char,     # Return type.
    ctypes.c_char_p,   # buffer
    ctypes.c_ulong)    # length

# must be of size argtypes (direction, string parameter name, default value)
#1 - Specifies an input parameter to the function.
#2 - Output parameter. The foreign function fills in a value.
#4 - Input parameter which defaults to the integer zero.
StartExtractionParamFlags = (1, "SampleRate", 0), (1, "PodNumber", 0), (1, "ClockMode",0)
GetNextDataParamFlags = (1, "buffer", 0), (1, "length", 0)

# the name is mangled because this was a C++ function, but it seems to have the appropriate calling convention
StartExtraction = StartExtractionProto (("?StartExtraction@@YGHIKI@Z", usbedBasicDll), StartExtractionParamFlags)
StopExtraction = StopExtractionProto (("?StopExtraction@@YGHXZ", usbedBasicDll))
ExtractBufferOverflow = ExtractBufferOverflowProto (("?ExtractBufferOverflow@@YGDXZ", usbedBasicDll))
ExtractionBufferCount = ExtractionBufferCountProto (("?ExtractionBufferCount@@YGKXZ", usbedBasicDll))
GetNextData = GetNextDataProto (("?GetNextData@@YGDPAEK@Z", usbedBasicDll), GetNextDataParamFlags)


# use a customer formatter to do raw text and add default values
class CustomerFormatter(argparse.ArgumentDefaultsHelpFormatter, argparse.RawTextHelpFormatter):
    pass

parser = argparse.ArgumentParser(formatter_class=CustomerFormatter,
                                 description=textwrap.dedent('''
    Control the USBEE DX capture process
    '''))

# 17 = 1Msps
# 27 = 2Msps
# 37 = 3Msps
# 47 = 4Msps
# 67 = 6Msps
# 87 = 8Msps
# 127 = 12Msps
# 167 = 16Msps
# 247 = 24Msps

parser.add_argument('pod', action='store', type=int,
    help='Identification number of the USBEE DX pod')
parser.add_argument('outfile', action='store', type=argparse.FileType('w'),
    help='path to the VCD file to write to, if not specified, the VCD will be dumped to a shared RAM for display in GTKWave', nargs='?')
parser.add_argument('-s', '--samplerate', type=int, action='store',
    help='Sampling rate in Msps', default=4, choices=[1,2,3,4,6,8,12,16,24])
parser.add_argument('-v','--verbose', action='store_true',
    help='Increase output verbosity')

my_args = parser.parse_args()

print(my_args)
finish = False

class gtkwaveshm:
    WAVE_PARTIAL_VCD_RING_BUFFER_SIZE = 1024*1024
    def __init__(self, idnumber):
        # code from gtkwave:
        #/* size *must* match in gtkwave */
        #define WAVE_PARTIAL_VCD_RING_BUFFER_SIZE (1024*1024)
        #shmid = getpid();
        #sprintf(mapName, "shmidcat%d", shmid);
        #hMapFile = CreateFileMapping(INVALID_HANDLE_VALUE, NULL, PAGE_READWRITE, 0, WAVE_PARTIAL_VCD_RING_BUFFER_SIZE, mapName);
        #if(hMapFile != NULL)
        #{
        #    buf_top = buf_curr = buf = MapViewOfFile(hMapFile, FILE_MAP_ALL_ACCESS, 0, 0, WAVE_PARTIAL_VCD_RING_BUFFER_SIZE);
        #    memset(buf, 0, WAVE_PARTIAL_VCD_RING_BUFFER_SIZE);
        self.shm = mmap.mmap(0, self.WAVE_PARTIAL_VCD_RING_BUFFER_SIZE, "shmidcat%d"%(idnumber,))
        # clear the shm
        for i in range(1024):
            self.shm.write("\x00" * 1024)
        self.shm.seek(0)
        self.buf_top = 0
        self.buf_curr = 0

    def __del__(self):
        self.close()

    def get_8(self, pos):
        if pos >= self.WAVE_PARTIAL_VCD_RING_BUFFER_SIZE:
            pos -= self.WAVE_PARTIAL_VCD_RING_BUFFER_SIZE
        return ord(self.shm[pos])

    def get_32(self, pos):
        rc = self.get_8(pos)      << 24
        rc += self.get_8(pos + 1) << 16
        rc += self.get_8(pos + 2) << 8
        rc += self.get_8(pos + 3)
        return rc

    def put_8(self, pos, val):
        if pos >= self.WAVE_PARTIAL_VCD_RING_BUFFER_SIZE:
            pos -= self.WAVE_PARTIAL_VCD_RING_BUFFER_SIZE
        self.shm[pos] = chr(val)

    def put_32(self, pos, val):
        self.put_8(pos,     val >> 24)
        self.put_8(pos + 1, val >> 16)
        self.put_8(pos + 2, val >> 8)
        self.put_8(pos + 3, val)
        
    def write(self, msg):
        # the layout of a block in shared RAM is the following:
        #  block[0] = valid byte (1 = valid/full, 0 = empty)
        #  block[1..5] = length of the block
        #  block[5..5+len] = payload
        length = len(msg)
        
        def inc_pos(pos, inc):
            pos += inc
            if pos >= self.WAVE_PARTIAL_VCD_RING_BUFFER_SIZE:
                pos -= self.WAVE_PARTIAL_VCD_RING_BUFFER_SIZE
            return pos
        while True:
            # look for the first empty block
            while True:
                b = self.get_8(self.buf_top)
                if b != 0:
                    # valid block not yet consumed, this is the upper limit
                    break
                blksiz = self.get_32(self.buf_top + 1)
                if blksiz == 0:
                    # block is 0, happens at the beginning
                    break
                else:
                    # move to the next block
                    self.buf_top = inc_pos(self.buf_top, 1 + 4 + blksiz)

            l_top = self.buf_top
            l_curr = self.buf_curr
            if l_curr >= l_top:
                consumed = l_curr - l_top
            else:
                consumed = l_curr + self.WAVE_PARTIAL_VCD_RING_BUFFER_SIZE - l_top
            if (consumed + length + 16) > self.WAVE_PARTIAL_VCD_RING_BUFFER_SIZE:
                # not enough space available to write -> wait before retrying
                time.sleep(0.01)
            else:
                self.put_32(self.buf_curr + 1, length)
                p = inc_pos(self.buf_curr, 1 + 4)
                if (p + length) < self.WAVE_PARTIAL_VCD_RING_BUFFER_SIZE:
                    self.shm[p:p + length] = msg
                else:
                    rem = self.WAVE_PARTIAL_VCD_RING_BUFFER_SIZE - p
                    self.shm[p:self.WAVE_PARTIAL_VCD_RING_BUFFER_SIZE] = msg[0:rem]
                    self.shm[0:length - rem] = msg[rem:]
                self.put_8(p + length, 0) # next valid byte
                self.put_32(p + length + 1, 0) # next len
                self.put_8(self.buf_curr, 1) # current valid
                self.buf_curr = inc_pos(self.buf_curr, 1 + 4 + length)
#                print("New buff : x%x"%self.buf_curr)
                break

    def close(self):
        try:
            self.shm.close()
        except AttributeError:
            print("shm was already closed")
    

def usbee_thread(args, q):
    SampleRate = ctypes.c_uint (args.samplerate * 10 + 7)
    PodNumber = ctypes.c_ulong (args.pod)
    ClockMode = ctypes.c_uint (2)
    
    if args.outfile == None:
        f = gtkwaveshm(int(str(args.pod), 16))
    else:
        f = args.outfile
    r = StartExtraction (SampleRate, PodNumber, ClockMode)
    print repr(r)

    if r == 1:
        # create the file
        f.write("$date\n")
        f.write("    " + time.strftime("%a %b %d %X %Y") + "\n")
        f.write("$end\n")
        f.write("$version\n")
        f.write("    Generated with pyusbee\n")
        f.write("$end\n")
        f.write("$comment\n")
        f.write("    Sampling rate = %d\n"%args.samplerate)
        f.write("$end\n")
        f.write("$timescale 1 ns $end\n")
        f.write("$scope module capture $end\n")
        f.write("$var wire 1 0 sig0 $end\n")
        f.write("$var wire 1 1 sig1 $end\n")
        f.write("$var wire 1 2 sig2 $end\n")
        f.write("$var wire 1 3 sig3 $end\n")
        f.write("$var wire 1 4 sig4 $end\n")
        f.write("$var wire 1 5 sig5 $end\n")
        f.write("$var wire 1 6 sig6 $end\n")
        f.write("$var wire 1 7 sig7 $end\n")
        f.write("$upscope $end\n")
        f.write("$enddefinitions $end\n")

        SAMPLE_BUFFER_LEN = 0x0100000

        cnt_buf = []
        cnt_buf_empty = 0

        b = ctypes.create_string_buffer(SAMPLE_BUFFER_LEN)
        cnt = 0
        last_value = -1
        
        # generate the translation table for the sample (0=b00000000 1=b000000001 ...)
        #sample = map(lambda x: "b{0:b} !\n".format(x), range(256))
        sample = map(lambda x: str(x) + "\n", range(8))

        # for the time being, just stop on the first transition
        while not finish:
            buflen = ExtractionBufferCount()
            if buflen > 0:
                if buflen > SAMPLE_BUFFER_LEN:
                    print("The buffer is too large %d"%buflen)
                    buflen = SAMPLE_BUFFER_LEN
                r = GetNextData(b, buflen)
                if ord(r) == 1:
                    #cnt_buf.append((buflen, cnt_buf_empty))
                    cnt_buf_empty = 0
                    # check if there was a transition
                    for c in b[:buflen]:
                        c = ord(c)
                        if c != last_value:
                            if last_value == -1:
                                f.write("$dumpvars\n")
                                for i in range(8):
                                    if c & (1 << i):
                                        f.write("1"+sample[i])
                                    else:
                                        f.write("0"+sample[i])
                                f.write("$end\n")
                            else:
                                # convert the sample number to time
                                f.write("#" + str(1000 * cnt / args.samplerate) + "\n")
                                x = c ^ last_value
                                for i in range(8):
                                    if x & (1 << i):
                                        if c & (1 << i):
                                            f.write("1"+sample[i])
                                        else:
                                            f.write("0"+sample[i])
                            last_value = c
                            
                        cnt += 1
                else:
                    print("Although the count was not null, the buffer was not retrieved")
            else:
                time.sleep(0.01)
                cnt_buf_empty += 1
        
        # print some statistics allowing to check the processor usage
        #print("cnt_buf = %d cnt = %d cnt_nobuf = %s"%(len(cnt_buf), cnt, cnt_buf))
        
        f.close()
        r = StopExtraction ()
        print repr(r)


class UsbeeCmd(cmd.Cmd):
    """Simple command processor example."""
    
    def do_stop(self, line):
        global finish
        finish = True

    def do_EOF(self, line):
        global finish
        finish = True
        return True

if __name__ == '__main__':
    print("starting thread")
    q = Queue.Queue()
    t = threading.Thread(target=usbee_thread, name="usbee_thread", args=(my_args, q))

    t.start()
    
    c = UsbeeCmd()
    c.cmdloop()

    print("waiting for thread to end")
    t.join()

