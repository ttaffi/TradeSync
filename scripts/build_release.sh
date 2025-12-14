#!/bin/bash
# TradeSync Release Builder
# Builds the macOS app and creates a DMG installer.

APP_NAME="TradeSync"
VERSION=$(grep '__version__' src/__init__.py | cut -d '"' -f 2)
DMG_NAME="TradeSync_v${VERSION}"
VOL_NAME="TradeSync Installer"

# Derived paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
DIST_DIR="$ROOT_DIR/dist"
BUILD_DIR="$ROOT_DIR/build"
SRC_DIR="$ROOT_DIR/src"
STATIC_DIR="$SRC_DIR/static"

SOURCE_APP="$DIST_DIR/${APP_NAME}.app"
SPARSE_IMG="$DIST_DIR/pack.sparseimage"
FINAL_DMG="$DIST_DIR/${DMG_NAME}.dmg"

BACKGROUND_IMG="$STATIC_DIR/dmg_background.png"
ICON_FILE="$STATIC_DIR/TradeSync.icns"

# Ensure we are in the root directory for PyInstaller
cd "$ROOT_DIR"

# 1. Clean previous builds and mounts
echo "🧹 Cleaning previous builds and mounts..."
hdiutil info | grep "/Volumes/$VOL_NAME" | cut -f1 | xargs -I {} hdiutil detach {} -force 2>/dev/null
rm -rf "$DIST_DIR" "$BUILD_DIR"

# 2. Build the Application
echo "🔨 Building TradeSync.app with PyInstaller..."
# Check if spec file exists
if [ ! -f "src/launcher.spec" ]; then
    echo "❌ Error: src/launcher.spec not found."
    exit 1
fi

pyinstaller src/launcher.spec --clean --noconfirm --distpath "$DIST_DIR" --workpath "$BUILD_DIR"

if [ ! -d "$SOURCE_APP" ]; then
    echo "❌ Error: Build failed. $SOURCE_APP not found."
    exit 1
fi


# 3. Create DMG
echo "📦 Creating DMG Installer..."

# Create Sparse Image (Writable)
hdiutil create "$SPARSE_IMG" -volname "$VOL_NAME" -fs HFS+ -type SPARSE -size 500m -layout SPUD

# Mount Sparse Image
DEVICE=$(hdiutil attach "$SPARSE_IMG" -readwrite -noverify -noautoopen | awk '/Apple_HFS/ {print $1}')
MOUNT_POINT="/Volumes/$VOL_NAME"

echo "   Mounted at $MOUNT_POINT"
sleep 2

# Copy App to DMG
echo "   Copying application..."
cp -R "$SOURCE_APP" "$MOUNT_POINT/"

# Create Symlink to Applications
ln -s /Applications "$MOUNT_POINT/Applications"

# Apply Finder Layout via AppleScript
echo "   Applying Finder layout..."
APP_SCRIPT="
   tell application \"Finder\"
     tell disk \"$VOL_NAME\"
         open
         delay 1
         
         set viewOptions to the icon view options of container window
         set arrangement of viewOptions to not arranged
         set icon size of viewOptions to 128
         
         set the bounds of container window to {100, 100, 700, 500}
         
         repeat 3 times
             set position of item \"$APP_NAME\" of container window to {160, 220}
             set position of item \"Applications\" of container window to {440, 220}
             delay 1
             update without registering applications
         end repeat
         
         close
         open
         update without registering applications
         delay 2
         close
     end tell
   end tell
"
echo "$APP_SCRIPT" | osascript

# Finalize Permissions
echo "   Finalizing permissions..."
chmod -Rf go-w "$MOUNT_POINT"
sync

# Unmount
echo "   Unmounting..."
hdiutil detach "$DEVICE" -force
sleep 2

# Convert to Final DMG
echo "   Compressing to $FINAL_DMG..."
if [ -f "$FINAL_DMG" ]; then rm "$FINAL_DMG"; fi
hdiutil convert "$SPARSE_IMG" -format UDZO -imagekey zlib-level=9 -o "$FINAL_DMG"

# Cleanup
rm -rf "$SPARSE_IMG"

echo "✅ Success! Release ready: $FINAL_DMG"
