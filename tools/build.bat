@echo off
setlocal

echo === Build: pyside6-deploy ===
pyside6-deploy --config-file pysidedeploy.spec
if errorlevel 1 (
  echo Build failed.
  exit /b 1
)

echo === Move DLL/PYD to bin ===
python tools\relocate_bins.py --auto
if errorlevel 1 (
  echo Relocate failed.
  exit /b 1
)

echo Done.
