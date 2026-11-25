# Heimdall R3 dual-camera shoulder mount

Copyright (C) 2026 BoreasLabs. Licensed under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

Open [`heimdall_r3_dual.scad`](../cad/heimdall_r3_dual.scad) in OpenSCAD. The
printable meshes are in [`stl/r3_dual`](../stl/r3_dual/), and the assembly
preview is [`heimdall_r3_preview.png`](./heimdall_r3_preview.png). R2 is
unchanged.

## Explicit design outputs

- Fixed provisional lens-center baseline: **27.00 mm**, measured horizontally
  from the thermal optical axis to the RGB optical axis.
- Both optical centers are at the same Z coordinate and both axes point along
  the same Y direction. The two PCB pockets share one front datum in a single
  rigid pod.
- Physical pod-to-Pi enclosure air gap: **17 mm**.
- Modeled CSI connector-to-connector route: **102 mm**, comprising the 17 mm
  enclosure gap, 20 mm inside the pod, 45 mm inside the Pi enclosure, and a
  20 mm service allowance.
- Published/supplied CSI ribbon length: **150 mm**, leaving **48 mm** reserve. The
  OpenSCAD source asserts that the selected ribbon is not shorter than the
  modeled route.
- Thermal horizontal field of view: **57 degrees**. Published RGB horizontal
  field of view: **66 degrees**. With parallel axes, the thermal angular field
  lies inside the RGB angular field; close objects still have parallax because
  the lens centers are 27.00 mm apart.
- At the 8 mm hood lip, the calculated clear diameters are **18.29 mm thermal**
  and **19.99 mm RGB**, including 0.8 mm radial margin. Each lens has its own
  non-overlapping drain-open hood.
- Both lenses use **open apertures** in this prototype. There is no clear RGB
  window, avoiding reflections and a new focus offset. A sealed clear window
  can be added after its thickness and optical quality are selected.

## Mechanical arrangement

The thermal and RGB boards sit side by side in separate close-tolerance edge
pockets. One rear lid presses both boards against the same front datum. The pod,
both apertures, both hoods, and the common mounting foot are one printed part.
The 0, 10, 20, and 25 degree wedges sit under that common foot, so a wedge moves
both cameras together. The pod is carried by an independent curved strap saddle
and remains thermally separated from the Pi saddle.

The fixed conduit has two lanes under one full-length removable screwed cover.
A full-height 2.4 mm divider separates the **18.5 mm CSI lane** from the
**15.5 mm GPIO lane**. The CSI lane is sized for the provisional 16 mm ribbon.
The GPIO lane remains sized for nine individual Dupont jumpers or a 10-conductor
ribbon. An overlapping pod tail keeps the lanes covered while the pod is used
with a pitch wedge. The camera-end clamp has a wide shallow CSI saddle and a
separate round GPIO saddle; it does not press the ribbon into a sharp fold.

The Pi GPIO housings remain captured by the screw-down comb. The only external
electrical exit is the USB-C power entry. The camera harnesses remain inside the
pod, divided conduit, Pi enclosure, and their removable covers.

The removable GPIO comb now spans a **55 mm-long full 2 x 20 Dupont housing
envelope**, allowing additional GPIO connections to be added later. Unscrew the
comb before installing or moving a jumper, then reinstall it at the measured
housing height.

The measured fan is **40 x 40 x 7.15 mm** with a **29.7 mm square mounting-hole
pattern**. The model positions it under the Pi lid and moves its center away from
the removable wire-channel seam; four M3 clearance holes now match that pattern.

## Published camera dimensions now used

All coordinates use the **lower-left PCB corner viewed from the lens side**.
The RGB values come from the official Camera Module 3 Standard mechanical
drawing RP-008153-DS-1 and the Arducam product listing:

- PCB: 25.0 x 23.862 x 1.12 mm.
- Total PCB-back-to-lens-front depth: 11.3 mm.
- Maximum forward lens housing diameter: 5.75 mm.
- Lens projection from the PCB front face: 10.18 mm.
- Lens center: X 12.5 mm, Y 14.4 mm.
- Four mounting holes: 2.2 mm diameter on a 21.0 x 12.5 mm pattern.
- CSI ribbon: standard 15-pin, 1 mm pitch, approximately 16 mm wide; the
  supplied Pi 4 cable is 150 mm long.
- RGB field of view: 66 degrees horizontal and 41 degrees vertical.

The photographed thermal board is the GroupGets PureThermal Breakout Board.
The GroupGets drawing gives a 25 x 24 mm PCB, 21 mm horizontal hole spacing,
approximately 12 mm vertical hole spacing, and 6 mm exposed header pins. The
FLIR Lepton package with socket is published as 11.8 x 12.7 x 7.2 mm. The
measured board thickness is **1.8 mm**. The submitted 3.5 mm X/Y readings
appear to describe mounting-hole offsets rather than the lens center, so the
exact installed Lepton optical center, lens-front clearance, mounting-hole
diameter, and actual jumper-housing envelope remain physical-fit measurements.

Changing any PCB outline or optical-center value can change the 27.00 mm
baseline. Re-export all pod-related parts and record the new echoed baseline
after entering caliper measurements.

## Print set

Print `base`, `camera_saddle`, `camera_pod`, `pi_lid`, `fan_cap`, `camera_lid`,
`channel_cover`, `gpio_clamp`, `camera_wire_clamp`, and one pitch wedge. Print
both coupons before the pod. Every exported R3 STL is a single watertight mesh
and fits within a 220 x 220 x 250 mm printer volume.

This remains a fit prototype. The installed thermal core, jumper housings,
strap, fan, inserts, and cable measurements marked for verification must be confirmed. The ribbon
path must be checked with the actual CSI connector position and a real ribbon
before field use. Test wedge movement with the overlap sleeve and confirm there
is no opening or ribbon contact at the chosen pitch. Verify sealing, airflow,
strain relief, connector-clamp pressure, visibility through both hoods, and
total equipped mass on the physical assembly.
