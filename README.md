# GPSparser

GPSparser is a Python GPS NMEA string parsing module.

This module provides GPS NMEA string parsing through the GPSString
class. A GPSstring is an object whose I{msg} is any ASCII text string
containing a NMEA GPS string somewhere within it. NMEA strings
characteristicly start with the leading "$" and end with the *hh where
hh is the two character checksum. All of the following examples are fine:

```
$GPGGA,154809.00,4305.52462642,N,07051.89568468,W,1,3,4.1,48.971,M,-32.985,M,,*54
RTK1_GPS         DATA    2008-11-21T15:48:10.510017      $GPGGA,154809.00,4305.52462642,N,07051.89568468,W,1,3,4.1,48.971,M,-32.985,M,,*5
09/12/2003,04:01:46.666,$GPGGA,040145.871,7117.3458,N,15700.3788,W,1,06,1.4,014.6,M,-000.4,M,,*50
posnav  2008:226:18:31:34.1365  $INGGA,183133.898,7120.91996,N,15651.72629,W,1,11,0.8,-1.06,M,,,,*19
```

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