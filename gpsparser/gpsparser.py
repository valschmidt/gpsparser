#!/usr/bin/env python
from __future__ import print_function  # Used for print function
# See :http://stackoverflow.com/questions/5574702/how-to-print-to-stderr-in-python
__version__ = "0.3.1"
__date__ = "27 Sept 2016"
__author__ = "Val Schmidt"
__doc__ = '''
GPSparser, a Python GPS NMEA String parsing module. 

This module provides GPS NMEA string parsing through the GPSString
class. A GPSstring is an object whose I{msg} is any ASCII text string
containing a NMEA GPS string somewhere within it. NMEA strings
characteristicly start with the leading "$" and end with the *hh where
hh is the two character checksum. All of the following examples are fine:

    - C{$GPGGA,154809.00,4305.52462642,N,07051.89568468,W,1,3,4.1,48.971,M,-32.985,M,,*54}
    - C{RTK1_GPS         DATA    2008-11-21T15:48:10.510017      $GPGGA,154809.00,4305.52462642,N,07051.89568468,W,1,3,4.1,48.971,M,-32.985,M,,*5}
    - C{09/12/2003,04:01:46.666,$GPGGA,040145.871,7117.3458,N,15700.3788,W,1,06,1.4,014.6,M,-000.4,M,,*50}
    - C{posnav  2008:226:18:31:34.1365  $INGGA,183133.898,7120.91996,N,15651.72629,W,1,11,0.8,-1.06,M,,,,*19}
    - C{1473622989.451 $GNGGA,194309.9,4308.15154,N,07056.35631,W,1,13,0.7,42.4,M,-31.9,M,,*43}

GPSparser provides methods for extracting the NMEA string from the
larger set of ASCII characters, verifying its checksum and parsing the
string's fields. The fields may then be accessed as attributes of GPSString
(i.e. C{GPSString.latitude}). The complete set of attributes available
after a string has been parsed can be found in the attribute list
C{GPSString.fieldnames}. Some fields are not returned, such as those that
provide units which, by standard or convention, never seem to change. 

GPSparser is designed for follow-on processing and plotting of values,
and therefore every effort is made to convert all fields to
meaningful, numeric values (objects of the Decimal Class). For example, Latitude and
Longitude are converted to decimal degrees to 10 digits past the
decimal point. Similarly, GPS fix type in RMC strings are indicated by an "A"
when the GPS has a fix and a "V" when it does not. These values are
reported by GPSParser as 1 and 0, respectively. 

Time in GPS strings are converted to datetime objects (see the
datetime module). Many NMEA strings contain time-of-day, but not date
(GGA for example). GPSparser will, by default, convert these strings
to datetime.time objects. However if the GPSString.date attribute is
set with a datetime.date object prior to calling the parse() method, a
full datetime.datetime object will be returned combining the supplied
date and time parsed from the string. This is a handy way to produce
full date-time stamps for each string.

A common thing to overlook, however, when parsing a file of strings
from a parent script, in which the times rotate over a UTC day, one
must be sure to also rotate the value used to set the GPSString.date
attribute.

When the module is called as a script, it will parse a file for a
single string type, which must be specified on the command-line (see
C{gpsparser.py -h}). The fields are written in tab-delimited format to
standard-out. Date-time stamps are written as tab-delimited vectors
(C{YYYY MM DD HH MM SS}). This format makes reading parsed data files
into Octave or MATLAB trivial ( C{load('datafile')} ), with the notable
exception of GSV strings which have variable numbers of fields
depending on the number of satellites tracked.

@author: '''+__author__+'''
@organization: Center for Coastal and Ocean Mapping, University of New Hampshire 
@version: ''' + __version__ +'''
@copyright: 2008-2016
@status: under development
@license: GPL

@bug: I've tried to handle several fields gracefully when they are commonly missing, but an empty line with a proper checksum, such as is common before a GPS has a fix will surely cause the code to fail. 

@todo: Unit tests. There are none so far and there needs to be. 
@todo: Add output in MATLAB .mat format.
@todo: Add output in HDF5 or NetCDF format.

'''
import os
import sys
import datetime
from datetime import timedelta
import re
#import string
import decimal as dec
#import pdb
from operator import xor
#import exceptions 

# A function for writing to standard error vs standard out. 
def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

class GPSString(object):
    '''
    A GPSString is any string that contains a complete NMEA string someplace 
    within it. The string must start with the leading $ and end with the *hh 
    where hh is the checksum. 
    '''
    GPS_IDs = { \
        'GGA' : 1, \
            'ZDA' : 2, \
            'RMC' : 3, \
            'GST' : 4, \
            'GSV' : 5, \
            'VTG' : 6, \
            'HDT' : 7 ,\
            'PASHR' : 8,\
            'GGK' : 9}


    def __init__(self,msg):
        '''
        Initializes the class with any string containing a single NMEA data string.

        @param msg: The ASCII string containing the NMEA data string.

        '''
        self.msg = msg
        'The message containing the gps string.'
        self.debug = False
        'A flag for writing debugging information'
        
        self.id = None

    def identify(self):
        '''
        This method identifies the string within gps_string, returning an ID index
        which is required to parse the string. 
        
        Currently the following message types are supported:
        GGA, ZDA, RMC, GST, GSV, VTG, HDT, PASHR, GGK
        '''
        'A dictionary of supported strings and their numeric indentifiers'

        for key in self.GPS_IDs.keys():
            if re.search( key, self.msg):
                # self.id = self.GPS_IDs[key]
                self.id = key
                return 

        raise NotImplementedError, ("This string is not recognized: " + self.msg)

    def parse(self):
        '''
        This method pareses a GPSString, defining a set of attributes for the class 
        with the parsing results. How each string is parsed is dependent on the
        type of string. In any case, the fields returned are defined in
        "self.fieldnames".

        Before parsing the string's checksum if verified. The GPSString.FailedChecksum 
        exception is raised if the checksum fails. [NOTE: The checksum verification
        may cause problems for some gps systems which do not calculate the checksum
        on the proper portion of the string. The NMEA standard specifies calculation 
        on the portions of the string  __between__ the leading "$" and "*", but 
        not to include either. ]

        A few general rules are in order. Time stamps are converted to datetime
        objects. Several GPS strings contain only time fields with no year, month,
        or day. If gps_string.date is defined with a datetime.date object (i.e.
        mygpsstring.date = datetime.date(2008,12,1) ) prior to calling the 
        parse() method, the final datetime object will combine the pre-set 
        date with the gps parsed time value. If gps_string.date is not defined
        the returned datetime object returned from the parse() method will 
        reflect the gps time as a datetime.time() object.

        Latitude and Longitude are converted to decimal degrees with negative 
        values for the Southern and Western hemispheres. They are reported to 8
        decimal places which equates to just over 1 mm precision.

        Some fields are not parsed because they do not typically change. The 
        units fields of meters for geoid separation in the GGA string is a classic
        example.

        '''

        ' Verify Checksum'
        if not self.checksum(True):
            raise self.FailedChecksum, ("Failed Checksum! Line: " + self.msg)


        if self.id == None:
            self.identify()

        ' Parse the code'
        if self.id == 'GGA':
            'GGA'
            exp = '(?P<match>\$..GGA.*)\*(?P<chksum>..)'
            m = re.search(exp,self.msg)
            if m:
                gps_extract = m.group('match')
                fields = gps_extract.split(',')

                'Handle GGA Fields'
                self.handlegpstime(fields[1])                
                self.handle_lat( fields[2], fields[3] )
                self.handle_lon ( fields[4], fields[5] )
                self.quality = dec.Decimal( fields[6] )
                self.svs = dec.Decimal( fields[7] )
                self.hdop = dec.Decimal( fields[8])
                try:
                    self.antennaheight = dec.Decimal(fields[9])
                except dec.InvalidOperation:
                    if self.debug:
                        eprint("The field antennaheight may not be present.")
                        eprint("self.msg")
                    self.antennaheight = dec.Decimal('NaN')
                try:
                    self.geoid = dec.Decimal(fields[11])
                except dec.InvalidOperation:
                    if self.debug:
                        eprint("The field GEOID Height may not be present.")
                        eprint(self.msg)
                        #print fields[11]
                    self.geoid = dec.Decimal('NaN')
                try:
                    self.dgpsage = dec.Decimal(fields[13])
                except dec.InvalidOperation:
                    if self.debug: 
                        eprint("The field DGPS Age may not be present.")
                        eprint(self.msg)                        
                        #print fields[13]
                    self.dgpspage = dec.Decimal('NaN')
                try:
                    self.stationid = dec.Decimal(fields[14] )
                except dec.InvalidOperation:
                    if self.debug: 
                        eprint("The field DGPS Station ID may not be present.")
                        eprint(self.msg)
                        #print 'StationID: %s' % fields[14]
                    self.stationid = dec.Decimal('NaN')
                        
            else:
                raise self.FailedParsing, 'Failed to parse %s' % self.msg
                
        elif self.id == 'ZDA':
            'ZDA'
            exp = '(?P<match>\$..ZDA.*)\*(?P<chksum>..)'
            m = re.search(exp,self.msg)
            if m:
                gps_extract = m.group('match')
                fields = gps_extract.split(',')
                'Handle ZDA Fields'
                self.datetime = datetime.date(int( fields[4]), \
                                                  int(fields[3]), \
                                                  int(fields[2]))
                self.handlegpstime(fields[1])
                try:
                    self.tzoffsethours = dec.Decimal( fields[5] )
                except dec.InvalidOperation:
                    if self.debug:
                        eprint("Thef ield Local TZ Offset Hours may not be present.")
                        eprint (fields[5])
                    self.tzoffsethours = dec.Decimal('NaN')

                try:
                    self.tzoffsetminutes = dec.Decimal( fields[6] )
                except dec.InvalidOperation:
                    if self.debug: 
                        eprint("The field Local TZ Offset Minutes may not be present.")
                        eprint(fields[6])
                    self.tzoffsetminutes = dec.Decimal('NaN')
            else:
                raise self.FailedParsing, 'Failed to parse %s' % self.msg
 

        elif self.id == 'RMC':
            'RMC' 
            exp = '(?P<match>\$..RMC.*)\*(?P<chksum>..)'
            m = re.search(exp,self.msg)
            if m:
                gps_extract = m.group('match')
                fields = gps_extract.split(',')
                'Handle RMC Fields'
                'Getting the date first ensure handlegpstime will return a full'
                'datetime object'      
                try:
                    self.datetime = datetime.date(int(fields[9][4:6])+2000,
                                                  int(fields[9][2:4]),
                                                  int(fields[9][0:2]))
                    self.handlegpstime(fields[1])
                    if fields[2] == 'A':
                        self.fixstatus = 1
                    else:
                        self.fixstatus = 0
                    self.handle_lat(fields[3], fields[4])
                    self.handle_lon(fields[5], fields[6])
                    self.knots = fields[7]
                    self.cog = fields[8]
                except:
                    raise self.FailedParsing, 'Failed to parse %s' % self.msg
            else:
                raise self.FailedParsing, 'Failed to parse %s' % self.msg
 
        elif self.id == 'GST':
            'GST'
            exp = '(?P<match>\$..GST.*)\*(?P<chksum>..)'
            m = re.search(exp,self.msg)
            if m:
                gps_extract = m.group('match')
                fields = gps_extract.split(',')
                'Handle GST Fields'
                self.handlegpstime(fields[1])
                self.residualrms = dec.Decimal(fields[2])
                self.semimajor = dec.Decimal(fields[3])
                self.semiminor = dec.Decimal(fields[4])
                self.orientation = dec.Decimal(fields[5])
                self.lat1sigma = dec.Decimal(fields[6])
                self.lon1sigma = dec.Decimal(fields[7])
                self.height1sigma = dec.Decimal(fields[8])
            else:
                raise self.FailedParsing, 'Failed to parse %s' % self.msg
 
        elif self.id == 'GSV':
            'GSV'
            exp = '(?P<match>\$..GSV.*)\*(?P<chksum>..)'
            m = re.search(exp,self.msg)
            if m:
                gps_extract = m.group('match')
                fields = gps_extract.split(',')
                'Handle GSV Fields'
                self.messages = dec.Decimal( fields[1] )
                self.messagenum = dec.Decimal ( fields[2] )
                self.visibleSVs = dec.Decimal ( fields[3] )
                self.PRN = []
                self.elevation = []
                self.azimuth = []
                self.snr = []
                if self.debug: 
                    eprint(fields)
                for idx in range(4,fields.__len__() - 1, 4):
                    self.PRN.append(dec.Decimal(fields[idx]))
                    self.elevation.append(dec.Decimal(fields[idx + 1]))
                    try:
                        self.azimuth.append(dec.Decimal(fields[idx + 2]))
                    except dec.InvalidOperation:
                        self.azimuth.append(dec.Decimal('NaN'))
                        eprint("The field Satellite Azimuth may be missing.")
                        eprint(fields[idx + 3])
                    try:
                        self.snr.append(dec.Decimal(fields[idx + 3]))
                    except dec.InvalidOperation:
                        # The spec says snr should be null when "not tracking"
                        self.snr.append(dec.Decimal('NaN'))
            else:
                raise self.FailedParsing, 'Failed to parse %s' % self.msg
 
        elif self.id == 'VTG':
            'VTG'
            exp = '(?P<match>\$..VTG.*)\*(?P<chksum>..)'
            m = re.search(exp,self.msg)
            if m:
                gps_extract = m.group('match')
                fields = gps_extract.split(',')
                'Handle VTG Fields'
                self.cog = dec.Decimal(fields[1])
                self.knots = dec.Decimal(fields[5])
                self.kmph = dec.Decimal(fields[7])
            else:
                raise self.FailedParsing, 'Failed to parse %s' % self.msg
                

        elif self.id == 'HDT':
            'HDT'
            exp = '(?P<match>\$..HDT.*)\*(?P<chksum>..)'
            m = re.search(exp,self.msg)
            if m:
                gps_extract = m.group('match')
                fields = gps_extract.split(',')
                'Handle HDT Fields'
                self.heading = fields[1]
            else:
                raise self.FailedParsing, 'Failed to parse %s' % self.msg
                 
                
        elif self.id == 'PASHR':
            'PASHR'
            exp = '(?P<match>\$PASHR.*)\*(?P<chksum>..)'
            m = re.search(exp,self.msg)
            if m:
                gps_extract = m.group('match')
                fields = gps_extract.split(',')
                'Handle PASHR Fields'
                self.handlegpstime(fields[1])
                self.heading = dec.Decimal(fields[2])
                self.roll = dec.Decimal(fields[4])
                self.pitch = dec.Decimal(fields[5])
                self.heave = dec.Decimal(fields[6])
                self.rollaccuracy = dec.Decimal(fields[7])
                self.pitchaccuracy = dec.Decimal(fields[8])
                self.headingaccuracy = dec.Decimal(fields[9])
                self.headingalgorithm = dec.Decimal(fields[10])
                self.imustatus = dec.Decimal(fields[11])
            else:
                raise self.FailedParsing, 'Failed to parse %s' % self.msg
 
        elif self.id == 'GGK':
            'GGK'
            exp = '(?P<match>\GGK.*)\*(?P<chksum>..)'
            m = re.search(exp,self.msg)
            if m:
                gps_extract = m.group('match')
                fields = gps_extract.split(',')
                'Handle GGK Fields'
                print(fields[2])
                print(fields[2][4:6])
                self.date = datetime.date(int(fields[2][4:6])+2000,
                                          int(fields[2][0:2]),
                                          int(fields[2][2:4]))
                self.handlegpstime(fields[1])
                self.handle_lat(fields[3],fields[4])
                self.handle_lon(fields[5],fields[6])
                self.quality = dec.Decimal(fields[7])
                self.svs = dec.Decimal(fields[8])
                self.dop = dec.Decimal(fields[9])
                self.eht = dec.Decimal(fields[10][3:fields[10].__len__()])
            else:
                raise self.FailedParsing, 'Failed to parse %s' % self.msg
               
        # Create a dictionary of the fields parsed.
        keys = self.__dict__.keys()
        keys.remove('debug')
        keys.remove('msg')
        keys.remove('id')
        self.fields = {}
        for item in keys:
            self.fields[item] = self.__getattribute__(item)

    def handlegpstime(self, timestr):
        '''
        An internal method to convert gps time strings to datetime.time objects 
        (default) or datetime.datetime objects when GPSString.date is pre-defined
        with a datetime.date object. 

        @param timestr: A NMEA time string of the form HHMMSS.SSS .

        Since many strings do not contain the date,
        defining the 'date' attribute of GPSString allows one to manually set 
        the date.
        '''
        tmptime = timestr
        hour = dec.Decimal(tmptime[0:2])
        try:
            minute = dec.Decimal(tmptime[2:4])
        except dec.InvalidOperation:
            print(timestr)
            print(tmptime[2:4])
            print(self.msg)
            sys.exit()
            
        seconds = int(dec.Decimal(tmptime[4:tmptime.__len__()]))
        microseconds = int( (dec.Decimal(tmptime[4:tmptime.__len__()]) - \
                                 dec.Decimal(seconds) ) * 1000000 )

        timeval = datetime.time(hour, minute, seconds, microseconds)

        try:
            self.datetime = datetime.datetime.combine(self.date, timeval)
        except:
            self.datetime = timeval

    def handle_lat(self,lattmp, lathem):
        '''
        Converts latitude strings of arbitrary precision to decimal degrees to
        10 decimal places of precision (about .000001 meters).

        @param lattmp: The NMEA latitude string. (DDMM.MMMM)
        @param lathem: The NMEA latitude hemisphere ('N'/'S')
        '''
        self.latitude = '%.10f' % (dec.Decimal(lattmp[0:2]) + 
                         dec.Decimal(lattmp[2:lattmp.__len__()]) / 60)
        self.latitude = dec.Decimal(self.latitude)
        if lathem == 'S':
            self.latitude = - self.latitude

    def handle_lon(self,lontmp, lonhem):
        '''
        Converts longitude strings of arbitrary precision to decimal degrees to
        10 decimal places of precision (about .000001 meters at the equator).

        @param lontmp: The NMEA longitude string. (DDDMM.MMMM)
        @param lonhem: The NMEA longitude hemisphere ('E'/'W')
        '''
        self.longitude = '%.10f' % (dec.Decimal(lontmp[0:3]) + 
                          dec.Decimal(lontmp[3:lontmp.__len__()]) / 60)
        self.longitude = dec.Decimal(self.longitude)
        if lonhem == 'W':
            self.longitude = - self.longitude

    def stripisotime(self):
        '''
        Strips an ISO 8601 time stamp from the GPSString and returns a datetime
        object.

        For many scientific applications GPS strings are logged with the 
        logging computer's date-time stamp. When these time stamps are in 
        ISO 8601 format, this method will extract and parse them, returning a
        datetime object. 
        '''

        # FIX: Should append .* + self.id to this regexp. 
        iso_exp = re.compile('(?P<year>\d\d\d\d)-(?P<month>\d\d)-(?P<day>\d\d)T(?P<hour>\d\\d):(?P<minute>\d\d):(?P<seconds>\d\d\.\d+)') 
        m = re.search(iso_exp,self.msg)
        if m:
            year =  int( m.group('year'))
            month = int( m.group('month'))
            day =   int( m.group('day'))
            hour =  int(m.group('hour'))
            minute = int(m.group('minute'))
            seconds = int(float(m.group('seconds')))
            microseconds = int( ( float(m.group('seconds')) - seconds ) * 1000000)
            dts = datetime.datetime(year, month, day, hour, minute, seconds, microseconds)
            return dts

    def stripepochtime(self):
        '''
        Strips an EPOCH time stamp from the GPSString and returns a datetime 
        object
        '''
        epoch_exp = re.compile('(?P<epochtime>\d+\.\d+).*\$??' + self.id)
        m = re.search(epoch_exp,self.msg)
        if m:
            epochtime = float(m.group('epochtime'))
            dts = datetime.datetime.utcfromtimestamp(epochtime)
        return dts

    def datetimevec(self,dts):
        '''
        Converts a datetime stamp in the form of a datetime object to a
        tab-delimited vector of numeric values.

        @param dts: A datetime object.

        For many scientific applications one often desires to import data into MATLAB
        or Octave. A simple way to do that is to produce a tab-delimited date time 
        stamp of the form:

        YYYY    MH    DD    HR    MN    SS

        whiich can be converted to MATLABs internal representation of time with 
        datevec(). This method returns such as time stamp from a datetime object.
        '''
        return "\t".join(map(str,( dts.year, dts.month, dts.day, dts.hour, dts.minute, float(dts.second) + float(dts.microsecond) / 1000000 )))

    def checksum(self, verify = False):
        ''' 
        A function to calculate and return a checksum of a NMEA string.
 
        @param verify: When specified as True, checksum returns True/False
        rather than the acutal checksum value. 

        '''
        exp = '(?P<match>\$.*)\*(?P<chksum>..)'
        m = re.search(exp,self.msg)
        if m:                
            data = m.group('match')
            tmp = map(ord, data[1:])
            checksum = hex(reduce(xor, tmp))
            if checksum.__len__() == 3:
                checksum = checksum[0:2] + '0' + checksum[2] 
            if verify:
                return checksum[2:4].upper() == m.group('chksum')
            else:
                return checksum[2:4].upper()



# I'm keeping this because I once had code that simply returned the checksum for
# a string (that may not be a well-formatted NMEA string) which is required above.
# I'm not convinced this level of generality is necessary or appropriate here just yet.

#        if data.find('*') != -1 :
#            hasstar = True
#            tmp = map(ord, data[1:data.index('*')])
#        else:
#            tmp = map(ord, data)
#            
#        checksum = reduce(xor, tmp)
#        checksum = hex(checksum)
#        return checksum[2:4]

    class FailedChecksum(Warning):
        '''
        A class creating the exception FailedChecksum, which is derived from the 
        standard exception.Warning. This exception is raised when a GPS string's
        checksum is incorrect indicating corruption to the data.  
        '''
        pass
    class FailedParsing(Warning):
        '''
        A class creating the eception FailedParsing, which is derived from the 
        standard exception Warning. This exception is raised then a GPS string 
        failes to parse correctly.
        '''



######################################################################################
######################## Module Code Ends Here. ######################################
######################################################################################

if __name__ == '__main__':

    gpstmp = GPSString('')
    supportedstrings = gpstmp.GPS_IDs.keys()
    supportedstrings.sort()
    supportedstrings = ' '.join(supportedstrings)

    ''' Handle options'''
    import argparse
    parser = argparse.ArgumentParser(description=("Parse GPS NMEA0183 ASCII "
    "text data file(s), to one of: "
    "1) stdout (default) "
    "2) a file of the same as the input filename appended with 'parsed_STR.txt' "
    "3) a user specified filename "
    "4) a MATLAB compatible .mat file. (not yet supported)"))
    
    group = parser.add_mutually_exclusive_group()
    group.add_argument('-f','--filename', dest='filename',action='store',
                            help='specify the filename, default stdin', default=sys.stdin)
    group.add_argument('-g','--directory', dest='directory',action='store',
                            help=('alternatively, specify a directory and a suffix '
                            'pattern (e.g. /path/::.gps). The directory will be '
                            'searched recursively and files matching the suffix '
                            'specified after :: will be parsed. The output will '
                            ' go to separate output files if -o <directory> or '
                            ' -o i is specified.' ), 
                            default="") 
    parser.add_argument('-s','--stringtype',dest='stringtype',action='store',
                           help=('specify which string to parse by specifying '
                           'the three-letter identifier (Currently supported '
                           'strings: '+ supportedstrings + ')'))
    parser.add_argument('-o', dest='output',action='store',
                        default=None,
                       help=('A directory or filename. If a directory, output' 
                       'data to a file within the specified directory having '
                       'a file name of directory/<inputfilename>_STR_parsed.txt)'
                       ' where STR is the specified string to parse. If a file' 
                       ' name, output to that explicit file. If -o is omitted,'
                       ' data is written to stdout.'))
    parser.add_argument('-m',dest='matflag',action='store_true',
                        help='Write the output file in MATLAB .mat format. (NOT YET SUPPORTED)',
                        default=False)
    parser.add_argument('-v',dest='verbose',action='count',
                         help='Verbose output. (-v, -vv, -vvv, etc.)')
            
    args = parser.parse_args()
    
    filename = args.filename
    directory = args.directory
    stringtype = args.stringtype
    verbose = args.verbose
    output = args.output
    matflag = args.matflag

            
    if verbose >= 1:
        print("Arguments:")
        arguments = vars(args)
        for key, value in arguments.iteritems():
            print("\t%s:\t\t%s" % (key,str(value)))

    if directory:       
        filestoprocess = []     
        directory, suffix = directory.split('::')
        if verbose >= 3:
            print("directory: " + directory)
            print("suffix:    " + suffix)
        for root,subFolders, files in os.walk(directory):
            for fileval in files:
                if fileval[-suffix.__len__():] == suffix:
                    filestoprocess.append(os.path.join(root,fileval))
    else:
        filestoprocess = [filename]

    if filestoprocess.__len__() == 0:
        print("No files found to process.")
        sys.exit()

    # Conditions are:
    # 1) No -o is specified, write to std out.
    # 2) -o is specified with a directory, write default file name to directory.
    # 3) -o is specified with a filename. Write to the filename. 
    outputtofile = False
    outfilename = None 
    saveto1file = False
    # If we specified some kind of output, set it up (otherwise stdout is default)
    if output:
        outputtofile = True
        # We can specify a directory. If so, set it as the output dir. 
        if os.path.isdir(output):
            outputdir = output  # outfilename will get set dyamamically based on input file name.
            if verbose >=1:
                print("Output directory: " + outputdir)
                print("Output filename: Not specified")

        # Or we can set a file name directly. Then set everything.
        # Two things could have happened here. Either the directory did not 
        # exist, or a filename was specified with it. Here we check to see that 
        # the directory exists, and if so, we assume that anything further is 
        # the requested filename. 
        elif os.path.isdir(os.path.dirname(output)):
            saveto1file = True
            outputdir = os.path.dirname(output)
            outfilename = os.path.basename(output)
            if verbose >= 1:
                print("Outputfilename: " + os.path.join(outputdir,outfilename))
                
        # Or quicklly specify the output directory as the input directory with an 'i'
        elif output == 'i':
            if directory:
                outputdir = directory
            else:
                outputdir = os.path.dirname(filename)
        else:
            eprint("The argument to -g is not 'i', a valid directory or a valid/filename")
            sys.exit()
            
    if matflag:
        try:
            import scipy as sci
            import scipy.io as sio
        except:
            print("Output to MATLAB file format requires the scipy module.")
            sys.exit()
                
    if not GPSString.GPS_IDs.has_key(stringtype):
        print ('Unsupported string type: ' + str(stringtype))
        sys.exit()
            
        
    def assign_fieldnames(stringtype):
        ''' A function to assing fieldnames when writing MATLAB structures.'''
        
        switcher = {
                    "GGA":['pctime',
                           'gpstime',
                           'latitude',
                           'longitude',
                           'quality',
                           'svs',
                           'hdop',
                           'antennaheight',
                           'geoid'],
                    "ZDA":['pctime',
                           'gpstime'],
                    "RMC":['pctime',
                           'gpstime',
                           'fixstatus',
                           'latitude',
                           'longitude',
                           'knots',
                           'cog'],
                    "GST":['pctime',
                           'gpstime',
                           'residualrms',
                           'semimajor',
                           'semiminor',
                           'orientation',
                           'lat1sigma',
                           'lon1sigma',
                           'height1sigma'],
                    "GSV":['pctime',
                           'PRN',
                           'elevation',
                           'azimuth',
                           'snr'],
                    "VTG":['pctime',
                           'cog',
                           'knots',
                           'kmph'],
                    "HDT":['pctime',
                           'heading'],
                    "PASHR": ['pctime',
                              'gpstime',
                              'heading',
                              'roll',
                              'pitch',
                              'heave',
                              'rollaccuracy',
                              'headingaccuracy',
                              'headingalgorithm',
                              'imustatus'],
                    "GGK":['pctime',
                           'gpstime',
                           'latitude',
                           'longitude',
                           'quality',
                           'svs',
                           'dop',
                           'eht']
        }
        
        return switcher.get(stringtype,"")
        

    def printfields(fieldstoprint,fid=None):
        ''' A function to print the fields under different circumstances.'''
        if fid:
            fid.write("\t".join(map(str,fieldstoprint)).expandtabs() + '\n')
        else:
            print("\t".join(map(str,fieldstoprint)).expandtabs())

    matlabepochplus1yr = datetime.datetime(1,1,1,0,0,0) 
    oneyr = timedelta(days=365)
    def datetime2mat(dts):
        ''' Converts a python datetime object to MATLAB serial time.
        
        MATLAB serial time is decimal days since Jan 1, 1900, 00:00:00'''
        
        # Note, these machinations are required because the datetime object does not 
        # support year 0. 
        global matlabepochplus1yr
        global oneyr
      
        dt = dts-matlabepochplus1yr
        return (dt.total_seconds()+oneyr.total_seconds())/86400
        

    # Set up data structures for saving to a MATLAB .mat file.
    if matflag:
        mat = {}
        data={}
        mat[stringtype] = data
        
        # Initialize space for saving data in numpy arrays. 
        # We need to know the fields we intend to save before we begin reading data.
        # and ideally the number of data points. Here we initalize 
        # assuming a maximum 10Hz rate for 1 day. Is there a way to quickly 
        # pre-read the file? Or do we have to check on every assignment and increase
        # the size if necessary? Or do we leave it as a constraint. 
        matfieldnames = assign_fieldnames(stringtype)
        for key in matfieldnames:
            data[key] = sci.zeroes((864000,1),'double')
            data[key].fill(sci.nan)

    if verbose >=3:
        print("Entering debug mode")


    #######################            
    # PROCESS THE FILE(s) #
    #######################
    for filename in filestoprocess:
        
        # Gives status to stdout only when output is not stdout.
        if verbose >=1 and outputtofile:
            print('Processing ' + filename)
        if filename != sys.stdin:
            filetoread = file(filename,'r')
        else:
            filetoread = filename
        
        # When FID is None we print to stdout, by default.
        # But if we're saving to a file and we've explcity chosen it,
        # Then the file may be open, in which case don't loose the fid.
        if not saveto1file:
            fid = None
            
        # Set up the output file name if output to a file is requested. 
        # The output may be of txt or .mat type.
        # By now the output directory (outputdir), is already specified.
        if outputtofile or matflag:
            if outfilename is not None:
                pass
            if outfilename == None and not matflag:
                outfilename = (os.path.basename(filename[0:-4]) +
                '_parsed_'+ stringtype +'.txt')
            elif outfilename == None and matflag:
                outfilename = (os.path.basename(filename[0:-4]) +
                '_parsed_'+ stringtype +'.mat')

            if verbose >=1:
                print("Writing to %s" % os.path.join(outputdir,outfilename))        

        # If we are saving to a txt file, open the file. 
        # If it is the first process in the list, always open it. 
        # If not, then only open a new file if not saving to a single file,
        # which would happen if the file name was explicitly set.
        if outputtofile and not matflag: 
            if filename == filestoprocess[0]:
                fid = file(os.path.join(outputdir,outfilename),'w')
            elif not saveto1file:
                fid = file(os.path.join(outputdir,outfilename),'w')

        # By setting outfilename to None here we force creation of a new 
        # output file for every input file. Otherwise a file for the first one 
        # is created and this over-written with subseqeunt ones. We could write 
        # all to a single file, but there are reasons we may not want to do this too.
        if not saveto1file:
            outfilename = None        
        
        for line in filetoread:
    
            gps = GPSString(line)
            if verbose >=3:
                gps.debug = verbose

                
            try:
                gps.identify()  # populates gps.id
                
            except NotImplementedError:
                if verbose >= 1:
                    sys.stderr.write('Unrecognized NMEA string: %s\n' % gps.msg)
                continue
            except:
                eprint("Unexpected error:", sys.exc_info()[0])
                raise
    
            if gps.debug:
                print('String Type: ' + gps.id)
    
            'Only handle string specified'
            if gps.id != stringtype:
                continue
    
            '''Since GPS NMEA strings have no date, we have to create one. If the
            data is timestaped with an ISO format time, then use that. If not, 
            use the system time.'''
            
            # This will die silently if there is not a pc timestamp or if it of unsupported type. 
            PCtime = gps.stripisotime()
            if PCtime == None:
                PCtime = gps.stripepochtime()
                
            # Many GPS strings have only a time stamp with no date. Here we try to 
            # use the date provided by a PC time stamp during the logging porcess.
            # If there is no PC time stamp, one can only guess at the date and 
            # assume it is today. 
            
            # FIX: Provide a way to force the date if it is known on the command 
            # line. 
            try:
                gps.date = PCtime.date()
            except:
                if gps.debug:
                    print("NO Time Stamping Found. Using today's date.")
                gps.date = datetime.datetime.utcnow().date()
            
            ''' Parse and write data.'''
            if gps.id == 'GGA':
    
                try: 
                    gps.parse()
                    if gps.debug:
                        print("Fields: " + ','.join(gps.fields.keys()))
                        
                except gps.FailedChecksum:
                    sys.stderr.write( "Failed Checksum: "
                                      " :: " + gps.msg + '\n') 
                    continue
                except gps.FailedParsing:
                    sys.stderr.write("Failed Parsing Line: %s" % line)
                    continue
                except:
                    eprint("Unexpected error:", sys.exc_info()[0])
                    raise
                    
                fieldstoprint = [gps.datetimevec(gps.datetime), 
                                 gps.latitude, 
                                 gps.longitude, 
                                 gps.quality,
                                 gps.svs, 
                                 gps.hdop, 
                                 gps.antennaheight,
                                 gps.geoid]
                if PCtime:
                    fieldstoprint.insert(0,gps.datetimevec(PCtime))
    
                printfields(fieldstoprint,fid)
                
    
            if gps.id == 'ZDA':
    
                try: 
                    gps.parse()
                except gps.FailedChecksum:
                    sys.stderr.write( "Failed Checksum: " + gps.checksum() + 
                                      " :: " + gps.msg + '\n') 
                    continue
                except gps.FailedParsing:
                    sys.stderr.write("Failed Parsing Line: %s" % line)
                    continue
                except:
                    eprint("Unexpected error:", sys.exc_info()[0])
                    raise
                    
                fieldstoprint = [gps.datetimevec(gps.datetime)]
    
                if PCtime:
                    fieldstoprint.insert(0,gps.datetimevec(PCtime))
    
                printfields(fieldstoprint,fid)
    
            if gps.id == 'RMC':
    
                try:
                    gps.parse()
                except gps.FailedChecksum:
                    sys.stderr.write( "Failed Checksum: " + gps.checksum() + 
                                      " :: " + gps.msg + '\n') 
                    continue
                except gps.FailedParsing:
                    sys.stderr.write("Failed Parsing Line: %s" % line)
                    continue
                except:
                    eprint("Unexpected error:", sys.exc_info()[0])
                    raise
                      
                fieldstoprint = [gps.datetimevec(gps.datetime),
                                 gps.fixstatus,
                                 gps.latitude,
                                 gps.longitude,
                                 gps.knots,
                                 gps.cog]
    
                if PCtime:
                    fieldstoprint.insert(0,gps.datetimevec(PCtime))
    
                printfields(fieldstoprint,fid)
    
            if gps.id == 'GST':
    
                try:
                    gps.parse()
                except gps.FailedChecksum:
                    sys.stderr.write( "Failed Checksum: " + gps.checksum() + 
                                      " :: " + gps.msg + '\n') 
                    continue
                except gps.FailedParsing:
                    sys.stderr.write("Failed Parsing Line: %s" % line)
                    continue
                except:
                    eprint("Unexpected error:", sys.exc_info()[0])
                    raise
                      
                fieldstoprint = [gps.datetimevec(gps.datetime),
                                 gps.residualrms,
                                 gps.semimajor,
                                 gps.semiminor,
                                 gps.orientation,
                                 gps.lat1sigma,
                                 gps.lon1sigma,
                                 gps.height1sigma]
                if PCtime:
                    fieldstoprint.insert(0,gps.datetimevec(PCtime))
    
                printfields(fieldstoprint,fid)
                                  
            if gps.id == 'GSV':
    
                try: 
                    gps.parse()
                except gps.FailedChecksum:
                    sys.stderr.write( "Failed Checksum: " + gps.checksum() + 
                                      " :: " + gps.msg + '\n') 
                    continue
                except gps.FailedParsing:
                    sys.stderr.write("Failed Parsing Line: %s" % line)
                    continue
                except:
                    eprint("Unexpected error:", sys.exc_info()[0])
                    raise
                      
                    
                fieldstoprint = [gps.datetimevec(PCtime),  
                                 gps.PRN,
                                 gps.elevation,
                                 gps.azimuth,
                                 gps.snr]
                                 
                printfields(fieldstoprint,fid)
    
    
            if gps.id == 'VTG':
                'VTG'
                try:
                    gps.parse()
                except gps.FailedChecksum:
                    sys.stderr.write( "Failed Checksum:" + gps.checksum() + 
                                      "::" + gps.msg + '\n') 
                    continue
                except gps.FailedParsing:
                    sys.stderr.write("Failed Parsing Line: %s" % line)
                    continue
                except:
                    eprint("Unexpected error:", sys.exc_info()[0])
                    raise
      
                fieldstoprint = [gps.datetimevec(PCtime),
                                gps.cog,
                                gps.knots,
                                gps.kmph]
                                
                printfields(fieldstoprint,fid)
            
            if gps.id == 'HDT':
                try:
                    gps.parse()
                except gps.FailedChecksum:
                    sys.stderr.write( "Failed Checksum:" + gps.checksum() + 
                                      "::" + gps.msg + '\n') 
                    continue
                except gps.FailedParsing:
                    sys.stderr.write("Failed Parsing Line: %s" % line)
                    continue
                except:
                    eprint("Unexpected error:", sys.exc_info()[0])
                    raise
                    
                fieldstoprint = [gps.datetimevec(PCtime),
                                 gps.heading]
                printfields(fieldstoprint,fid)
                
                                 
            if gps.id == 'PASHR':
                try:
                    gps.parse()
                except gps.FailedChecksum:
                    sys.stderr.write( "Failed Checksum:" + gps.checksum() + 
                                      "::" + gps.msg + '\n') 
                    continue
                except gps.FailedParsing:
                    sys.stderr.write("Failed Parsing Line: %s" % line)
                    continue
                except:
                    eprint("Unexpected error:", sys.exc_info()[0])
                    raise
                
                fieldstoprint = [gps.datetimevec(gps.datetime),
                                 gps.heading,
                                 gps.roll,
                                 gps.pitch,
                                 gps.heave,
                                 gps.rollaccuracy,
                                 gps.headingaccuracy,
                                 gps.headingalgorithm,
                                 gps.imustatus]
                if PCtime:
                    fieldstoprint.insert(0,gps.datetimevec(PCtime))
                      
                printfields(fieldstoprint,fid)
              
            if gps.id == 'GGK':
                'GGK'
                try:
                    gps.parse()
                except gps.FailedChecksum:
                    sys.stderr.write( "Failed Checksum:" + gps.checksum() + 
                                      "::" + gps.msg + '\n') 
                except gps.FailedParsing:
                    sys.stderr.write("Failed Parsing Line: %s" % line)
                    continue
                except:
                    eprint("Unexpected error:", sys.exc_info()[0])
                    raise
      
                fieldstoprint = [gps.datetimevec(gps.datetime), 
                                 gps.latitude, 
                                 gps.longitude, 
                                 gps.quality,
                                 gps.svs, 
                                 gps.dop, 
                                 gps.eht]
                printfields(fieldstoprint,fid)
        
        ###############################################################
        ##### END READING FILE ########################################
        ###############################################################
                
        if outputtofile and not saveto1file:
            fid.close()
