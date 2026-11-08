"""Release version shared by the application and platform builds.

Version policy: substantial feature or UI changes increment the second
component (1.9 -> 1.10), resetting the third component. Small image-processing
algorithm improvements increment the third component (1.9 -> 1.9.1 -> 1.9.2).
Documentation-only changes do not increment the version.
"""
VERSION = '1.11.4'
