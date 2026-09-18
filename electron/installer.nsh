; Keep the standard NSIS uninstaller and expose it next to the app in Start.
; Engine/model caches and sessions are deliberately outside $INSTDIR.
!macro customInstall
  CreateShortCut "$SMPROGRAMS\Uninstall SoundShredder.lnk" "$INSTDIR\${UNINSTALL_FILENAME}" "/currentuser" "$INSTDIR\${UNINSTALL_FILENAME}" 0
!macroend

!macro customUnInstall
  Delete "$SMPROGRAMS\Uninstall SoundShredder.lnk"
!macroend

!macro customUnWelcomePage
  !define MUI_WELCOMEPAGE_TITLE "Uninstall SoundShredder"
  !define MUI_WELCOMEPAGE_TEXT "This removes the SoundShredder application and its shortcuts.$\r$\n$\r$\nYour saved sessions, downloaded audio engines and model caches will be kept for a future reinstall. Files you exported elsewhere will also remain.$\r$\n$\r$\nFinish or cancel any processing, then quit all SoundShredder windows before continuing."
  !insertmacro MUI_UNPAGE_WELCOME
!macroend
