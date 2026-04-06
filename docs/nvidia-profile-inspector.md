# Feature request

## High level scope
1. Save a copy of Nvidia exportCurrentProfile for BACKUP before applying all changes
2. During spec ingestion Check if G-Sync monitor is available, if availble, Use nvidiaProfileinspector to enable blur busters "best g-sync configuration";
2.1. enable g-sync
2.2. enable vsync
2.3. enable frame rate limit (Monitor_FPS_Cap) using this forumula
(Monitor_FPS_Cap=Refresh Rate−(Refresh_Rate×Refresh_Rate/4096))

For example, on a 240Hz monitor, the calculation yields:
240−(240×240/4096)=226 FPS
On a 360Hz monitor, the formula yields:
360−(360×360/4096)≈328 FPS
4)Enable ReBar (Resizeable Bar)

3. DLSS Settings per your GPU based on settings configurations
e.g. 50series should use DLSS4.5 preset K

## helpful command
Run `nvidiaProfileInspector.exe -exportCurrentProfile nv_profile.nip`.

### Documentation add to claude.MD
1. https://stepmodifications.org/wiki/Guide:NVIDIA_Inspector
2. https://www.pcgamingwiki.com/wiki/Nvidia_Profile_Inspector

## Questions
1. nvidiaProfileInspector.exe sourcing — where does the binary come from? (GitHub release? Bundled?) - 
1.1 Binary, use gh cli to access copy latests source code from https://github.com/Orbmu2k/nvidiaProfileInspector
1.2 copy it into ~/tools/
1.3 update build.py to include this build as part of the application
2. Alternative approaches — CLI profile editing vs. direct registry writes vs. NVAPI
2.1 The existing infrastructure should handle those changes, nvidiaProfileinspector has the option to enable additonal settings not avaialble through other methods.
2.2 high-level, copy current nvidiaprofileinspector profile to the Current working dir of lil_bro.exe and have it as a 'backup'
2.3 make required changes (g-sync, vsync,etc) using nvidiaprofileinspector
3. The trust surface question — the original design doc deferred this specifically because bundling adds trust surface with no v1 benefit. What changed?. 
3.1 Lets add more features to make the program robust as the current program is minial in what it does
4. AMD graceful degradation — what do AMD users see?
4.1 If during device identification a users card is AMD it will be ignored for now and inform user that AMD support will be added in the future after adoption
5. DLSS preset data source — where does the GPU gen → preset mapping come from?
5.1 I will provide the best presets based on information found on reddit and other sources. 
5.2 This data will be stored in the python source and fed into the program on build
6. ReBar via profile vs. BIOS — these are two separate toggles -
6.1  ReBar has some toggles that can be enabled in windows
6.2 Remaining settings must be setup in bios and lil_bro provides information that information to the users on how to complete it.			
			
			
