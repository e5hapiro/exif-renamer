# exif-renamer
Utilize EXIFTool to identify label and headline and if both tags exist copies file to a new directory

Purpose

exif-renamer is a python application custom designed to walk through a directory, locate media files that have been labeled, confirm that a headline exists, and if so it will batch copy all media files that are labeled and headlined to a destination directory along with any associated xmp sidecar files.  The program uses EXIFTool open source to read the IPTC core metadata from the file and/or its associated side car. 

Funtionality

Default root and destination directories are included in the code but can be overridden with command line parameters.

If a directory is passed, then the directory is appended to the root.

The Exiftool only works with media files, so the python script is limited to those files. 

Dependencies

Exiftool must be installed