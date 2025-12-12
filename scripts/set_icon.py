#!/usr/bin/env python3
import Cocoa
import sys

def set_icon(icon_path, target_path):
    # Load image
    image = Cocoa.NSImage.alloc().initWithContentsOfFile_(icon_path)
    if not image:
        return False
        
    # Standardize to 512x512
    image.setSize_(Cocoa.NSSize(512, 512))
    
    # Workaround: Convert to TIFF representation to ensure alpha is handled correctly by Finder
    tiff_data = image.TIFFRepresentation()
    bitmap = Cocoa.NSBitmapImageRep.imageRepWithData_(tiff_data)
    
    # Re-create image from bitmap
    final_image = Cocoa.NSImage.alloc().init()
    final_image.addRepresentation_(bitmap)
    
    return Cocoa.NSWorkspace.sharedWorkspace().setIcon_forFile_options_(final_image, target_path, 0)

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: set_icon.py <icon.icns> <target_file>")
        sys.exit(1)
    
    success = set_icon(sys.argv[1], sys.argv[2])
    if success:
        print(f"Icon set for {sys.argv[2]}")
    else:
        print(f"Failed to set icon for {sys.argv[2]}")
        sys.exit(1)
