# NPI Integration — Open Items

These must be resolved before the implementation can be completed.

- These are completed, review the /docs/NPI_Base_Profile_Export_Example.nip

---

## 1. The Assignment — Export a real .nip profile

1.1. All HEXCodes to change NPI Values are stored in /docs/NPI_CustomSettingNames.xml
1.2 nvidiaProfileInspector.exe doesn't currently offer a CLI arguemnt to export all profiles on a machine.
1.3 I've edited NPI source code to now include -exportCustomized to export all current customized settings to a .nip to the current working dir
1.4 Open the XML, and identify the exact hex setting IDs for:

- G-Sync enable

		<CustomSetting>
			<UserfriendlyName>GSYNC - Support Indicator Overlay</UserfriendlyName>
			<HexSettingID>0x008DF510</HexSettingID>
			<GroupName>2 - Sync and Refresh</GroupName>
			<SettingValues>
				<CustomSettingValue>
					<UserfriendlyName>Off</UserfriendlyName>
					<HexValue>0x00000000</HexValue>
				</CustomSettingValue></SettingValues>
	</CustomSetting>
	<CustomSetting>
    <UserfriendlyName>GSYNC - Indicator Overlay</UserfriendlyName>
			<HexSettingID>0x10029538</HexSettingID>
			<MinRequiredDriverVersion>331.00</MinRequiredDriverVersion>
			<GroupName>2 - Sync and Refresh</GroupName>
			<SettingValues>
				<CustomSettingValue>
					<UserfriendlyName>Off</UserfriendlyName>
					<HexValue>0x00000000</HexValue>
				</CustomSettingValue></SettingValues>
    </CustomSetting>
    	<CustomSetting>
        <UserfriendlyName>GSYNC - Application Mode</UserfriendlyName>
			<HexSettingID>0x1194F158</HexSettingID>
			<MinRequiredDriverVersion>331.00</MinRequiredDriverVersion>
			<GroupName>2 - Sync and Refresh</GroupName>
			<SettingValues>
				<CustomSettingValue>
					<UserfriendlyName>Fullscreen only</UserfriendlyName>
					<HexValue>0x00000001</HexValue>
				</CustomSettingValue></SettingValues>
    </CustomSetting>
    	<CustomSetting>
        <UserfriendlyName>GSYNC - Global Mode</UserfriendlyName>
			<HexSettingID>0x1094F1F7</HexSettingID>
			<MinRequiredDriverVersion>331.00</MinRequiredDriverVersion>
			<GroupName>2 - Sync and Refresh</GroupName>
			<SettingValues>
			
				<CustomSettingValue>
					<UserfriendlyName>Fullscreen only</UserfriendlyName>
					<HexValue>0x00000001</HexValue>
				</CustomSettingValue>
    </SettingValues>
			
    </CustomSetting>
    <UserfriendlyName>GSYNC - Global Feature</UserfriendlyName>
			<HexSettingID>0x1094F157</HexSettingID>
			<MinRequiredDriverVersion>331.00</MinRequiredDriverVersion>
			<GroupName>2 - Sync and Refresh</GroupName>
			<SettingValues>
				<CustomSettingValue>
					<UserfriendlyName>On</UserfriendlyName>
					<HexValue>0x00000001</HexValue>
				</CustomSettingValue>
			</SettingValues>
    <CustomSetting>
    	<UserfriendlyName>GSYNC - Application State</UserfriendlyName>
			<HexSettingID>0x10A879CF</HexSettingID>
			<MinRequiredDriverVersion>331.00</MinRequiredDriverVersion>
			<GroupName>2 - Sync and Refresh</GroupName>
			<SettingValues>
				<CustomSettingValue>
					<UserfriendlyName>Allow</UserfriendlyName>
					<HexValue>0x00000000</HexValue>
				</CustomSettingValue>
                	</SettingValues>
    </CustomSetting>
    	<CustomSetting>
        <UserfriendlyName>GSYNC - Application Requested State</UserfriendlyName>
			<HexSettingID>0x10A879AC</HexSettingID>
			<MinRequiredDriverVersion>331.00</MinRequiredDriverVersion>
			<GroupName>2 - Sync and Refresh</GroupName>
			<SettingValues>
				<CustomSettingValue>
					<UserfriendlyName>Allow</UserfriendlyName>
					<HexValue>0x00000000</HexValue>
				</CustomSettingValue>
                	</SettingValues>
    </CustomSetting>

- VSync mode - To enable use these settings
    	<CustomSetting>
        <UserfriendlyName>Vertical Sync - Smooth AFR Behavior</UserfriendlyName>
			<HexSettingID>0x101AE763</HexSettingID>
			<MinRequiredDriverVersion>310.00</MinRequiredDriverVersion>
			<GroupName>2 - Sync and Refresh</GroupName>
			<SettingValues>
				<CustomSettingValue>
					<UserfriendlyName>Off</UserfriendlyName>
					<HexValue>0x00000000</HexValue>
				</CustomSettingValue>
                
                	</SettingValues>
    </CustomSetting>
    	<CustomSetting>
        <UserfriendlyName>Vertical Sync</UserfriendlyName>
			<HexSettingID>0x00A879CF</HexSettingID>
			<GroupName>2 - Sync and Refresh</GroupName>
			<SettingValues>
				
				<CustomSettingValue>
					<UserfriendlyName>Force on</UserfriendlyName>
					<HexValue>0x47814940</HexValue>
				</CustomSettingValue>
            
                	</SettingValues>
    </CustomSetting>
    	<CustomSetting>
        <UserfriendlyName>Vertical Sync - Tear Control</UserfriendlyName>
			<HexSettingID>0x005A375C</HexSettingID>
			<MinRequiredDriverVersion>300.00</MinRequiredDriverVersion>
			<GroupName>2 - Sync and Refresh</GroupName>
			<SettingValues>
				<CustomSettingValue>
					<UserfriendlyName>Standard</UserfriendlyName>
					<HexValue>0x96861077</HexValue>
				</CustomSettingValue>
                </SettingValues>
    </CustomSetting>

- Frame rate limiter value - This will require indepth look at the NPI_CusomSettings to extract FPS based on the users max Hz monitor, lets extract the most frequent ones, 60hz, 120hz, 144hz 165hz 180hz, 240hz 360hzz 500hz
    	<CustomSetting>
        <UserfriendlyName>Frame Rate Limiter V3</UserfriendlyName>
			<HexSettingID>0x10835002</HexSettingID>
			<MinRequiredDriverVersion>441.87</MinRequiredDriverVersion>
			<GroupName>2 - Sync and Refresh</GroupName>
			<SettingValues>
			<CustomSettingValue>
					<UserfriendlyName>226 FPS</UserfriendlyName>
					<HexValue>0x000000E2</HexValue>
				</CustomSettingValue>
                </SettingValues>
    </CustomSetting>

- DLSS preset, enable custom and pick dlss letter
<CustomSetting>
			<UserfriendlyName>DLSS - Forced Model Preset Profile</UserfriendlyName>
			<HexSettingID>0x00634291</HexSettingID>
			<GroupName>5 - Common</GroupName>
			<MinRequiredDriverVersion>0</MinRequiredDriverVersion>
			<Description>If "Forced Preset Letter" has no effect, this setting may need to be changed for the game to apply the custom preset.</Description>
			<SettingValues>
				<CustomSettingValue>
					<UserfriendlyName>Custom</UserfriendlyName>
					<HexValue>0x00000002</HexValue>
				</CustomSettingValue>
			</SettingValues>
			<SettingMasks/>
		</CustomSetting>
<CustomSetting>
			<UserfriendlyName>DLSS - Forced Preset Letter</UserfriendlyName>
			<HexSettingID>0x10E41DF3</HexSettingID>
			<GroupName>5 - Common</GroupName>
			<MinRequiredDriverVersion>0</MinRequiredDriverVersion>
			<Description>NOTE: "DLSS - Forced Model Preset Profile" setting may need to be changed for this to apply on certain games.\r\nIf set, overrides the DLSS preset/model used across all quality levels (may not be desirable on some levels).</Description>
			<SettingValues>
				<CustomSettingValue>
					<UserfriendlyName>N/A</UserfriendlyName>
					<HexValue>0x00000000</HexValue>
				</CustomSettingValue>
				<CustomSettingValue>
					<UserfriendlyName>Preset A (CNN)</UserfriendlyName>
					<HexValue>0x00000001</HexValue>
				</CustomSettingValue>
				<CustomSettingValue>
					<UserfriendlyName>Preset B (CNN)</UserfriendlyName>
					<HexValue>0x00000002</HexValue>
				</CustomSettingValue>
				<CustomSettingValue>
					<UserfriendlyName>Preset C (CNN)</UserfriendlyName>
					<HexValue>0x00000003</HexValue>
				</CustomSettingValue>
				<CustomSettingValue>
					<UserfriendlyName>Preset D (CNN)</UserfriendlyName>
					<HexValue>0x00000004</HexValue>
				</CustomSettingValue>
				<CustomSettingValue>
					<UserfriendlyName>Preset E (CNN)</UserfriendlyName>
					<HexValue>0x00000005</HexValue>
				</CustomSettingValue>
				<CustomSettingValue>
					<UserfriendlyName>Preset F (CNN)</UserfriendlyName>
					<HexValue>0x00000006</HexValue>
				</CustomSettingValue>
				<CustomSettingValue>
					<UserfriendlyName>Preset G (unused)</UserfriendlyName>
					<HexValue>0x00000007</HexValue>
				</CustomSettingValue>
				<CustomSettingValue>
					<UserfriendlyName>Preset H (unused)</UserfriendlyName>
					<HexValue>0x00000008</HexValue>
				</CustomSettingValue>
				<CustomSettingValue>
					<UserfriendlyName>Preset I (unused)</UserfriendlyName>
					<HexValue>0x00000009</HexValue>
				</CustomSettingValue>
				<CustomSettingValue>
					<UserfriendlyName>Preset J (Transformer Gen 1)</UserfriendlyName>
					<HexValue>0x0000000A</HexValue>
				</CustomSettingValue>
				<CustomSettingValue>
					<UserfriendlyName>Preset K (Transformer Gen 1)</UserfriendlyName>
					<HexValue>0x0000000B</HexValue>
				</CustomSettingValue>
				<CustomSettingValue>
					<UserfriendlyName>Preset L (Transformer Gen 2)</UserfriendlyName>
					<HexValue>0x0000000C</HexValue>
				</CustomSettingValue>
				<CustomSettingValue>
					<UserfriendlyName>Preset M (Transformer Gen 2)</UserfriendlyName>
					<HexValue>0x0000000D</HexValue>
				</CustomSettingValue>
				<CustomSettingValue>
					<UserfriendlyName>Preset N (unused)</UserfriendlyName>
					<HexValue>0x0000000E</HexValue>
				</CustomSettingValue>
				<CustomSettingValue>
					<UserfriendlyName>Preset O (unused)</UserfriendlyName>
					<HexValue>0x0000000F</HexValue>
				</CustomSettingValue>
				<CustomSettingValue>
					<UserfriendlyName>Use recommended preset</UserfriendlyName>
					<HexValue>0x00FFFFFF</HexValue>
				</CustomSettingValue>
			</SettingValues>
			<SettingMasks/>
		</CustomSetting>
- ReBar driver toggle
    	<CustomSetting>
<UserfriendlyName>rBAR - Enable</UserfriendlyName>
			<HexSettingID>0x000F00BA</HexSettingID>
			<GroupName>5 - Common</GroupName>
			<AlternateNames>ReBAR - Enable, Resizable Bar - Enable</AlternateNames>
			<SettingValues>
				<CustomSettingValue>
					<UserfriendlyName>Disabled</UserfriendlyName>
					<HexValue>0x00000000</HexValue>
				</CustomSettingValue>
				<CustomSettingValue>
					<UserfriendlyName>Enabled</UserfriendlyName>
					<HexValue>0x00000001</HexValue>
				</CustomSettingValue>
			</SettingValues>
    </CustomSetting>


Save the annotated file to `docs/vendor-supplied/sample_npi_profile.nip`.

This also resolves **Open Item 4** (import CLI flag) — determine whether NPI supports partial/merge import or requires full-profile export → modify in-memory → reimport.

---

## 2. DLSS Preset Mapping

Founder to confirm the definitive GPU generation → DLSS version + preset letter mapping. Placeholder structure:

| GPU Series | DLSS Version | Preset |
|---|---|---|
| RTX 50-series | 4.5 | L |
| RTX 40-series | 4.5 | L |
| RTX 30-series | 4.5 | K |
| RTX 20-series | 4.5 | K |

2.1 To-do add individual gpu preset model recommendations
---

## 3. FPS Cap Formula

Design doc specifies: `cap = refresh_hz - (refresh_hz * refresh_hz / 4096)`

Examples:
- 144 Hz → 139 FPS
- 240 Hz → 226 FPS
- 360 Hz → 328 FPS
- 480 Hz → 424 FPS

---

## 4. NPI Import CLI Flag

1. Export the .nip containing all the profiles currently saved to the PC.
2. Keep that .nip in backup folder incase errors
3. Copy the .nip and modify required fields
4. Import .nip using `nvidiaProfileInspector.exe -silentImport "C:/path_to_file.nip"`

This determines the complexity of the fix functions in `src/agent_tools/nvidia_profile.py`.
