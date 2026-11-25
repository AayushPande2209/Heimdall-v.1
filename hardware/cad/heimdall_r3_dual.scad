/* SPDX-License-Identifier: CERN-OHL-W-2.0
   Copyright (C) 2026 BoreasLabs

   Heimdall R3 — rigid dual-camera shoulder pod prototype, mm.
   PART: assembly, base, camera_saddle, camera_pod, pi_lid, fan_cap, camera_lid,
         channel_cover, gpio_clamp, camera_wire_clamp,
         pitch_wedge_0, pitch_wedge_10, pitch_wedge_20, pitch_wedge_25,
         thermal_coupon, rgb_coupon.
   Both cameras share one locating pod and one pitch interface.
   Values marked GUESS must be replaced after caliper measurements.
*/
PART = "assembly";
$fn = 48;

// Hardware and fit: values marked GUESS require calipers.
slip = 0.25; press_interference = 0.05; wall = 2.4; eps = 0.06;
pi_x = 85; pi_y = 56; pi_t = 1.4;
pi_hole_x = [3.5,61.5]; pi_hole_y = [3.5,52.5]; // official Pi 4 DXF
pi_standoff_h = 5; pi_usb_h = 16; pi_eth_h = 13.5;
pi_port_overhang = 3; gpio_h = 8.5; jumper_h = 15;
gpio_body_x = 55; gpio_body_y = 5.2; // full 2x20 Dupont envelope with clearance
gpio_cx = 32.5-pi_x/2; gpio_cy = 52.5-pi_y/2; // DXF pin rows
gpio_connector_top = 3+pi_standoff_h+pi_t+gpio_h+jumper_h; // GUESS housing stack
// GroupGets PureThermal Breakout Board datasheet 1.3 + FLIR Lepton data.
cam_pcb_x = 25; cam_pcb_y = 24; cam_pcb_t = 1.8; // measured
cam_holes_x = 21; cam_holes_y = 12; cam_hole_d = 2.2; // diameter VERIFY
cam_lens_x = 12.5; cam_lens_y = 14.5; // core position VERIFY against STEP/part
cam_lens_d = 8; cam_lens_projection = 7.2; // lens diameter VERIFY
cam_socket_h = 3; cam_header_h = 15; // GUESS
cam_module_x = 11.8; cam_module_y = 12.7; cam_module_z = 7.2; // approximate
fov_h = 57; fov_v = 44; optical_margin = 0.8;

// Camera Module 3 Standard official mechanical drawing RP-008153-DS-1.
// Lower-left coordinates are viewed from the lens side.
rgb_pcb_x = 25; rgb_pcb_y = 23.862; rgb_pcb_t = 1.12;
rgb_total_depth = 11.3; // PCB back to lens front
rgb_lens_d = 5.75; // maximum forward lens housing diameter
rgb_lens_projection = rgb_total_depth-rgb_pcb_t;
rgb_lens_x = 12.5; rgb_lens_y = 14.4;
rgb_hole_d = 2.2;
rgb_hole_pattern_x = 21; rgb_hole_pattern_y = 12.5;
rgb_fov_h = 66; rgb_fov_v = 41;
rgb_ribbon_w = 16; rgb_ribbon_total_len = 150; // supplied 15 cm Pi 4 cable
camera_board_gap = 2;

// Side-by-side board and optical layout. These values create a fixed baseline.
dual_board_span_x = cam_pcb_x+camera_board_gap+rgb_pcb_x;
thermal_pcb_cx = -dual_board_span_x/2+cam_pcb_x/2;
rgb_pcb_cx = dual_board_span_x/2-rgb_pcb_x/2;
thermal_lens_cx = thermal_pcb_cx+(cam_lens_x-cam_pcb_x/2);
rgb_lens_cx = rgb_pcb_cx+(rgb_lens_x-rgb_pcb_x/2);
optical_baseline = rgb_lens_cx-thermal_lens_cx;
strap_w = 35; strap_t = 4; // GUESS
usb_cable_d = 4.5; dupont_bundle_w = 13; // GUESS
gpio_lane_w = dupont_bundle_w+2*slip+2; // 9 jumpers or 10-way ribbon
csi_lane_w = rgb_ribbon_w+2*slip+2; // dedicated CSI ribbon lane
channel_divider_t = wall;
wire_channel_w = gpio_lane_w+csi_lane_w+channel_divider_t;
wire_channel_h = 11; min_wire_bend_r = 10; service_loop_r = 11;
insert_d = 4.2; insert_h = 5; m3_clearance = 3.4; // insert maker TBD
fan_w = 40; fan_h = 7.15; fan_hole_pitch = 29.7; // measured
fan_cx = 35.5; fan_cy = -10; fan_air_d = 34;
fan_cap_w = 42; fan_cap_gap = 4; fan_cap_t = 2.4;
fan_cap_peg_pitch = 30;
fan_cap_peg_d = 4; fan_cap_peg_len = 2.5;

// Wearable geometry and enclosure levels.
shoulder_r = 105; plate_x = 138; plate_y = 86; plate_t = 3.2;
strap_slot_w = 7; strap_slot_l = strap_w+2; strap_slot_x = 59;
pi_clear = 3.5; pi_box_x = pi_x+2*pi_clear+pi_port_overhang+2*wall;
pi_box_y = pi_y+2*8+2*wall; // side bay for GPIO clamp posts
pi_wall_h = 47; pi_floor = 3; pi_lid_t = 3;
camera_box_x = dual_board_span_x+2*(wall+slip)+8;
camera_box_z = cam_pcb_y+2*(wall+slip)+8;
camera_box_depth = 29;
camera_face_t = max(cam_lens_projection,rgb_lens_projection)+2;
camera_center_x = 0; camera_center_z = 40;
pod_mount_x_spacing = camera_box_x-14;
pod_mount_y_spacing = camera_box_depth-10;
pod_mount_plate_t = 3;
pod_mount_plate_z = 4.5;
common_optical_z = camera_center_z+cam_lens_y-cam_pcb_y/2;
rgb_pcb_cz = common_optical_z-(rgb_lens_y-rgb_pcb_y/2);
pi_front_y = -pi_box_y/2;
camera_rear_y = pi_front_y-17; // 17 mm free air except narrow conduit
camera_front_y = camera_rear_y-camera_box_depth;
camera_plate_y = camera_front_y-2;
camera_plate_x = 56; camera_plate_l = 52;
channel_x = gpio_cx;
// Lane centers within the shared outer conduit. A solid divider keeps the
// fragile CSI ribbon mechanically isolated from the GPIO harness.
csi_lane_center_x = channel_x-(gpio_lane_w+channel_divider_t)/2;
divider_center_x = channel_x+(csi_lane_w-gpio_lane_w)/2;
gpio_lane_center_x = channel_x+(csi_lane_w+channel_divider_t)/2;
channel_back_y = gpio_cy+8;
channel_front_y = camera_rear_y+1;
channel_len = channel_back_y-channel_front_y;
channel_y = (channel_back_y+channel_front_y)/2;
channel_floor_z = 33;
channel_top_z = channel_floor_z+wire_channel_h+wall;
channel_out_w = wire_channel_w+2*wall;
loop_bay_inner_r = service_loop_r+wire_channel_w/2;
cover_out_w = channel_out_w+14;
cover_t = 2.4;
cam_optical_face_y = camera_front_y+2; // GUESS lens recessed 2mm
hood_lip_y = camera_front_y-6;

// Ribbon length budget: connector-to-connector routing, including a 20 mm
// service allowance. The physical enclosure air gap is separate and smaller.
pod_to_pi_air_gap = pi_front_y-camera_rear_y;
csi_pod_internal_run = 20;
csi_pi_internal_run = 45;
csi_service_allowance = 20;
csi_required_len = pod_to_pi_air_gap+csi_pod_internal_run+
                   csi_pi_internal_run+csi_service_allowance;

function thermal_cone_h(d) = cam_lens_d+2*(d*tan(fov_h/2)+optical_margin);
function thermal_cone_v(d) = cam_lens_d+2*(d*tan(fov_v/2)+optical_margin);
function rgb_cone_h(d) = rgb_lens_d+2*(d*tan(rgb_fov_h/2)+optical_margin);
function rgb_cone_v(d) = rgb_lens_d+2*(d*tan(rgb_fov_v/2)+optical_margin);
thermal_aperture_d = max(cam_module_y+2*slip,thermal_cone_h(2));
thermal_hood_d = max(thermal_cone_h(8),thermal_cone_v(8));
rgb_aperture_d = max(rgb_lens_d+2*slip,rgb_cone_h(2));
rgb_hood_d = max(rgb_cone_h(8),rgb_cone_v(8));
echo(str("FIXED OPTICAL BASELINE: ",optical_baseline," mm"));
echo(str("PHYSICAL POD-TO-PI AIR GAP: ",pod_to_pi_air_gap," mm"));
echo(str("REQUIRED CSI RIBBON ROUTE: ",csi_required_len," mm; provisional cable: ",
         rgb_ribbon_total_len," mm; reserve: ",rgb_ribbon_total_len-csi_required_len," mm"));
echo(str("Thermal hood opening: ",thermal_hood_d,
         " mm; RGB hood opening: ",rgb_hood_d," mm"));
assert(rgb_ribbon_total_len >= csi_required_len,
       "CSI ribbon is shorter than the modeled connector-to-connector route");

module rounded(x,y,z,r=3) {
  linear_extrude(height=z) offset(r=r) square([x-2*r,y-2*r],center=true);
}
module slot(d,l,h) {
  hull() for(y=[-(l-d)/2,(l-d)/2]) translate([0,y,0])
    cylinder(d=d,h=h,center=true);
}
module curved_plate(x,y) {
  intersection() {
    translate([0,y/2,-shoulder_r]) rotate([90,0,0])
      difference() {
        cylinder(r=shoulder_r,h=y);
        translate([0,0,-eps]) cylinder(r=shoulder_r-plate_t,h=y+2*eps);
      }
    translate([-x/2,-y/2,-15]) cube([x,y,18]);
  }
}
module plate_slots(xoff) {
  for(x=[-xoff,xoff]) translate([x,0,-5])
    slot(strap_slot_w,strap_slot_l,20);
}
module pi_holes() {
  for(x=pi_hole_x) for(y=pi_hole_y)
    translate([x-pi_x/2,y-pi_y/2,0]) children();
}
module pi_lid_screws() {
  for(x=[-pi_box_x/2+6,pi_box_x/2-6])
    for(y=[-pi_box_y/2+6,pi_box_y/2-6])
      translate([x,y,0]) children();
}
module cam_lid_screws() {
  for(x=[-camera_box_x/2+5,camera_box_x/2-5])
    for(z=[camera_center_z-camera_box_z/2+5,camera_center_z+camera_box_z/2-5])
      translate([x,0,z]) children();
}
module pod_mount_screws() {
  for(x=[-pod_mount_x_spacing/2,pod_mount_x_spacing/2])
    for(y=[-pod_mount_y_spacing/2,pod_mount_y_spacing/2])
      translate([x,y,0]) children();
}

// Two open, front-facing apertures. Both optical centers share common_optical_z.
// The RGB lens also stays open; a clear window can be added later without
// changing the pod, but the prototype avoids reflections and focus shift.
module optical_cut() {
  translate([thermal_lens_cx,camera_front_y-eps,common_optical_z])
    rotate([-90,0,0])
      cylinder(d=thermal_aperture_d,h=camera_face_t+2*eps);
  translate([thermal_lens_cx,hood_lip_y-eps,common_optical_z])
    rotate([-90,0,0])
      cylinder(d1=thermal_hood_d,d2=thermal_aperture_d,
               h=camera_front_y-hood_lip_y+2*eps);
  translate([rgb_lens_cx,camera_front_y-eps,common_optical_z])
    rotate([-90,0,0])
      cylinder(d=rgb_aperture_d,h=camera_face_t+2*eps);
  translate([rgb_lens_cx,hood_lip_y-eps,common_optical_z])
    rotate([-90,0,0])
      cylinder(d1=rgb_hood_d,d2=rgb_aperture_d,
               h=camera_front_y-hood_lip_y+2*eps);
}
module one_camera_hood(lens_x,ap_d,hood_open_d) {
  translate([lens_x,hood_lip_y,common_optical_z])
    rotate([-90,0,0]) difference() {
      cylinder(d1=hood_open_d+2*wall,d2=ap_d+2*wall,
               h=camera_front_y-hood_lip_y+0.3);
      translate([0,0,-eps]) cylinder(d1=hood_open_d,d2=ap_d,
                                      h=camera_front_y-hood_lip_y+0.5);
      // Open lower quadrant lets water run off the lens path.
      translate([0,hood_open_d/2,-1])
        cube([hood_open_d+4,hood_open_d,12],center=true);
    }
}
module camera_hood() {
  one_camera_hood(thermal_lens_cx,thermal_aperture_d,thermal_hood_d);
  one_camera_hood(rgb_lens_cx,rgb_aperture_d,rgb_hood_d);
}

// Both strap plates are distinct. Only the narrow hollow conduit joins pods.
module base() {
  difference() {
    union() {
      difference() { curved_plate(plate_x,plate_y); plate_slots(strap_slot_x); }
      // Pi tray, flat floor and open top.
      translate([0,0,-1]) rounded(pi_box_x+5,pi_box_y+5,4,5);
      difference() {
        rounded(pi_box_x,pi_box_y,pi_wall_h,5);
        translate([0,0,pi_floor])
          rounded(pi_box_x-2*wall,pi_box_y-2*wall,pi_wall_h+1,2.5);
      }
      pi_holes() translate([0,0,pi_floor]) cylinder(d=6.6,h=pi_standoff_h);
      pi_lid_screws() translate([0,0,pi_wall_h-insert_h])
        cylinder(d=8,h=insert_h);
      // GPIO clamp support outside the PCB edge, with vertical insert seats.
      for(x=[gpio_cx-gpio_body_x/2-5,gpio_cx+gpio_body_x/2+5])
        translate([x,pi_y/2+6,pi_floor])
          cylinder(d=7,h=gpio_connector_top+2-pi_floor);

      // Thin U conduit, including the air gap. No other solid bridge.
      translate([0,0,channel_floor_z]) difference() {
        linear_extrude(height=wire_channel_h+wall)
          translate([channel_x,channel_y])
            square([channel_out_w,channel_len+2*wall],center=true);
        translate([0,0,wall])
          linear_extrude(height=wire_channel_h+eps)
            translate([channel_x,channel_y])
              square([wire_channel_w,channel_len+2*wall+2],center=true);
      }
      // Full-height divider makes the CSI ribbon lane mechanically separate.
      translate([divider_center_x,channel_y,
                 channel_floor_z+wall+wire_channel_h/2])
        cube([channel_divider_t,channel_len+2*wall,
              wire_channel_h],center=true);
      // Captive insert seats for service cover at each end.
      for(y=[channel_front_y+4,channel_back_y-4])
        for(x=[channel_x-channel_out_w/2-3,
               channel_x+channel_out_w/2+3])
          translate([x,y,channel_floor_z]) cylinder(d=7,h=12);
    }
    // Pi mount screws and underside captive M2.5 nut pockets.
    pi_holes() {
      translate([0,0,1.7]) cylinder(d=3,h=pi_floor+pi_standoff_h);
      translate([0,0,-eps]) cylinder(d=5.8,h=2.1,$fn=6);
    }
    pi_lid_screws() translate([0,0,pi_wall_h-insert_h])
      cylinder(d=insert_d,h=insert_h+eps);
    for(x=[gpio_cx-gpio_body_x/2-5,gpio_cx+gpio_body_x/2+5])
      translate([x,pi_y/2+6,gpio_connector_top+2-insert_h])
        cylinder(d=insert_d,h=insert_h+eps);
    // Ports only at the two enclosure walls; conduit floor stays intact.
    for(y=[pi_front_y,camera_rear_y])
      translate([channel_x,y,channel_floor_z+wall+wire_channel_h/2])
        cube([wire_channel_w,wall+4,wire_channel_h],center=true);
    // All service-cover insert pilots remain above wire tray.
    for(y=[channel_front_y+4,channel_back_y-4])
      for(x=[channel_x-channel_out_w/2-3,
             channel_x+channel_out_w/2+3])
        translate([x,y,channel_floor_z+12-insert_h])
          cylinder(d=insert_d,h=insert_h+eps);
    // One USB-C power entry only, through the Pi rear wall.
    translate([-pi_box_x/2+16,pi_box_y/2,16])
      rotate([90,0,0]) cylinder(d=usb_cable_d+2*slip,h=wall+3,center=true);
    // Internal pair of cable tie slots provides power strain relief.
    for(y=[pi_box_y/2-11,pi_box_y/2-20])
      translate([-pi_box_x/2+16,y,pi_floor/2])
        cube([3,4,pi_floor+1],center=true);
    // Downward-facing vent passages below the Pi lid overhang.
    for(x=[-24:8:24])
      translate([x,pi_box_y/2,pi_wall_h-8])
        cube([4,wall+3,5],center=true);
  }
}

module camera_saddle() {
  // Independent curved strap saddle preserves the Pi-to-camera air gap.
  difference() {
    union() {
      translate([0,camera_plate_y,0])
        difference() {
          curved_plate(camera_plate_x,camera_plate_l);
          plate_slots(camera_plate_x/2-8);
        }
      translate([0,(camera_front_y+camera_rear_y)/2,-6])
        pod_mount_screws() cylinder(d=8,h=12);
    }
    translate([0,(camera_front_y+camera_rear_y)/2,1])
      pod_mount_screws() cylinder(d=insert_d,h=insert_h+eps);
  }
}

module camera_pod() {
  difference() {
    union() {
      // One continuous shell and front datum rigidly locates both cameras.
      difference() {
        translate([0,(camera_front_y+camera_rear_y)/2,camera_center_z])
          cube([camera_box_x,camera_box_depth,camera_box_z],center=true);
        translate([0,(camera_front_y+camera_face_t+camera_rear_y+1)/2,
                   camera_center_z])
          cube([camera_box_x-2*wall,
                camera_rear_y-camera_front_y-camera_face_t+1,
                camera_box_z-2*wall],center=true);
      }
      // A single mounting plate and four struts carry the entire pod.
      translate([0,(camera_front_y+camera_rear_y)/2,pod_mount_plate_z])
        cube([camera_box_x-6,camera_box_depth-5,pod_mount_plate_t],center=true);
      for(x=[-camera_box_x/2+7,camera_box_x/2-7])
        for(y=[camera_front_y+6,camera_rear_y-6])
          translate([x,y,pod_mount_plate_z])
            cylinder(d=7,h=camera_center_z-camera_box_z/2-pod_mount_plate_z+1);

      // Rear lid and strain-relief insert bosses stay outside both PCBs.
      for(x=[-camera_box_x/2+5,camera_box_x/2-5])
        for(z=[camera_center_z-camera_box_z/2+5,
               camera_center_z+camera_box_z/2-5])
          translate([x,camera_rear_y-7,z])
            rotate([-90,0,0]) cylinder(d=8,h=7);
      for(x=[-camera_box_x/2+6,camera_box_x/2-6])
        translate([x,camera_rear_y-4,channel_floor_z+2])
          cylinder(d=8,h=6);
      // Overlapping tail keeps both lanes enclosed while a pitch wedge tilts
      // the pod. It sleeves over the fixed chassis conduit without pinching.
      translate([channel_x,camera_rear_y+4,
                 channel_floor_z+wall+(wire_channel_h+wall)/2])
        difference() {
          cube([channel_out_w+2*slip,10,
                wire_channel_h+wall+2*slip],center=true);
          cube([wire_channel_w+2*slip,11,
                wire_channel_h+2*slip],center=true);
        }
      camera_hood();
      for(x=[-camera_box_x/2+3,camera_box_x/2-3])
        for(z=[camera_center_z-camera_box_z/2+3,
               camera_center_z+camera_box_z/2-3])
          translate([x,hood_lip_y-1,z])
            rotate([-90,0,0]) cylinder(d=6,h=camera_box_depth+7);
    }
    optical_cut();

    // Board edge pockets define the baseline and common optical plane. The
    // common rear lid presses both PCBs against the same machined front datum.
    translate([thermal_pcb_cx,camera_rear_y-0.2,camera_center_z])
      cube([cam_pcb_x+2*slip,8,cam_pcb_y+2*slip],center=true);
    translate([rgb_pcb_cx,camera_rear_y-0.2,rgb_pcb_cz])
      cube([rgb_pcb_x+2*slip,8,rgb_pcb_y+2*slip],center=true);

    for(x=[-camera_box_x/2+5,camera_box_x/2-5])
      for(z=[camera_center_z-camera_box_z/2+5,
             camera_center_z+camera_box_z/2-5])
        translate([x,camera_rear_y-insert_h,z])
          rotate([-90,0,0]) cylinder(d=insert_d,h=insert_h+eps);
    for(x=[-camera_box_x/2+6,camera_box_x/2-6])
      translate([x,camera_rear_y-4,channel_floor_z+8-insert_h])
        cylinder(d=insert_d,h=insert_h+eps);

    // The split conduit enters without exposing either cable. Clearance is
    // above the closing face, and the divider continues into the pod.
    translate([channel_x,camera_rear_y-1,
               channel_floor_z+wall+wire_channel_h/2])
      cube([wire_channel_w,10,wire_channel_h],center=true);
    translate([0,(camera_front_y+camera_rear_y)/2,pod_mount_plate_z-2])
      pod_mount_screws() cylinder(d=m3_clearance,h=8);
  }
  translate([divider_center_x,camera_rear_y-4,
             channel_floor_z+(wire_channel_h+wall)/2])
    cube([channel_divider_t,8,wire_channel_h+wall+2*slip],center=true);
  // Bridge the divider to the overlap sleeve's roof after the rear opening
  // has been cut, preventing a loose internal strip in the printed pod.
  translate([divider_center_x,camera_rear_y+4,
             channel_floor_z+wire_channel_h+wall+1.1])
    cube([channel_divider_t,10,4],center=true);
}

module pitch_wedge(angle=0) {
  wedge_x = camera_box_x-6;
  wedge_y = camera_box_depth-5;
  wedge_min_h = 3;
  wedge_rise = wedge_y*tan(angle);
  difference() {
    hull() {
      translate([-wedge_x/2,-wedge_y/2,0])
        cube([wedge_x,1,wedge_min_h]);
      translate([-wedge_x/2,wedge_y/2-1,0])
        cube([wedge_x,1,wedge_min_h+wedge_rise]);
    }
    // Long holes tolerate the screw-axis shift while the complete pod tilts.
    pod_mount_screws()
      translate([0,0,-eps]) slot(m3_clearance,7,
                                 wedge_min_h+abs(wedge_rise)+2);
  }
}

module pi_lid() {
  difference() {
    union() {
      translate([0,0,pi_wall_h])
        rounded(pi_box_x+2*(wall+slip),pi_box_y+2*(wall+slip),pi_lid_t,5);
      // Short internal lip stops the lid from walking.
      translate([0,0,pi_wall_h-3])
        difference() {
          rounded(pi_box_x-2*slip,pi_box_y-2*slip,3,4);
          translate([0,0,-eps])
            rounded(pi_box_x-2*wall-2*slip,
                    pi_box_y-2*wall-2*slip,3+2*eps,2);
        }
    }
    pi_lid_screws() translate([0,0,pi_wall_h-4])
      cylinder(d=m3_clearance,h=pi_lid_t+8);
    translate([fan_cx,fan_cy,pi_wall_h-1])
      cylinder(d=fan_air_d,h=pi_lid_t+3);
    // Measured 29.7 mm square fan pattern. Fan mounts under the lid.
    for(x=[fan_cx-fan_hole_pitch/2,fan_cx+fan_hole_pitch/2])
      for(y=[fan_cy-fan_hole_pitch/2,fan_cy+fan_hole_pitch/2])
        translate([x,y,pi_wall_h-eps])
          cylinder(d=m3_clearance,h=pi_lid_t+2*eps);
    for(x=[fan_cx-fan_cap_peg_pitch/2,fan_cx+fan_cap_peg_pitch/2])
      for(y=[fan_cy-fan_cap_peg_pitch/2,fan_cy+fan_cap_peg_pitch/2])
        translate([x,y,pi_wall_h-eps])
          cylinder(d=fan_cap_peg_d+2*slip,h=pi_lid_t+2*eps);
    // Open service-channel seam; the separate cover overlaps this opening.
    translate([channel_x,0,pi_wall_h+pi_lid_t/2])
      cube([cover_out_w+2,pi_box_y+2,pi_lid_t+2],center=true);
  }
}

module fan_cap() {
  // Drip roof: open 4 mm perimeter gap supplies fan air from the sides.
  difference() {
    union() {
      translate([fan_cx,fan_cy,pi_wall_h+pi_lid_t+fan_cap_gap])
        rounded(fan_cap_w,fan_cap_w,fan_cap_t,4);
      for(x=[fan_cx-fan_cap_peg_pitch/2,fan_cx+fan_cap_peg_pitch/2])
        for(y=[fan_cy-fan_cap_peg_pitch/2,fan_cy+fan_cap_peg_pitch/2])
          translate([x,y,pi_wall_h+pi_lid_t-fan_cap_peg_len])
            cylinder(d=fan_cap_peg_d,
                     h=fan_cap_peg_len+fan_cap_gap+fan_cap_t);
    }
  }
}

module camera_lid() {
  // One rear cover clamps both cameras against the shared front datum.
  difference() {
    union() {
      translate([0,camera_rear_y+wall/2,camera_center_z])
        cube([camera_box_x+2*wall,wall,camera_box_z+2*wall],center=true);
      // Four stops per PCB retain board edges without loading either lens.
      thermal_hold_l = camera_box_depth-camera_face_t-cam_pcb_t-0.5;
      rgb_hold_l = camera_box_depth-camera_face_t-rgb_pcb_t-0.5;
      for(x=[thermal_pcb_cx-cam_pcb_x/2+2,
             thermal_pcb_cx+cam_pcb_x/2-2])
        for(z=[camera_center_z-cam_pcb_y/2+2,
               camera_center_z+cam_pcb_y/2-2])
          translate([x,camera_rear_y-thermal_hold_l/2,z])
            cube([3,thermal_hold_l,3],center=true);
      for(x=[rgb_pcb_cx-rgb_pcb_x/2+2,
             rgb_pcb_cx+rgb_pcb_x/2-2])
        for(z=[rgb_pcb_cz-rgb_pcb_y/2+2,
               rgb_pcb_cz+rgb_pcb_y/2-2])
          translate([x,camera_rear_y-rgb_hold_l/2,z])
            cube([3,rgb_hold_l,3],center=true);
    }
    for(x=[-camera_box_x/2+5,camera_box_x/2-5])
      for(z=[camera_center_z-camera_box_z/2+5,
             camera_center_z+camera_box_z/2-5])
        translate([x,camera_rear_y-4,z]) rotate([-90,0,0])
          cylinder(d=m3_clearance,h=8);
    // Conduit enters from rear; its cover overlaps this cut.
    translate([channel_x,camera_rear_y-1,
               channel_floor_z+wall+wire_channel_h/2])
      cube([wire_channel_w,10,wire_channel_h],center=true);
  }
}

module channel_cover() {
  difference() {
    union() {
      translate([channel_x,channel_y,channel_top_z+cover_t/2])
        cube([cover_out_w,channel_len+8,cover_t],center=true);
      // Side lips stay outside the loose conductors.
      for(x=[channel_x-channel_out_w/2+wall/2,
             channel_x+channel_out_w/2-wall/2])
        translate([x,channel_y,channel_top_z-0.6])
          cube([wall-2*slip,channel_len+4,1.2],center=true);
    }
    for(y=[channel_front_y+4,channel_back_y-4])
      for(x=[channel_x-channel_out_w/2-3,
             channel_x+channel_out_w/2+3])
        translate([x,y,channel_top_z-4])
          cylinder(d=m3_clearance,h=8);
    // Two left rain-cap pegs seat into the cover, outside the wire trough.
    for(y=[fan_cy-fan_cap_peg_pitch/2,fan_cy+fan_cap_peg_pitch/2])
      translate([fan_cx-fan_cap_peg_pitch/2,y,channel_top_z-1])
        cylinder(d=fan_cap_peg_d+2*slip,h=cover_t+3);
  }
}

module gpio_clamp() {
  // Captures the female jumper housings, screwed to two chassis posts.
  clamp_x = gpio_body_x+16;
  difference() {
    union() {
      translate([gpio_cx,pi_y/2+4,gpio_connector_top+1])
        cube([clamp_x,15,2.4],center=true);
      // Shallow comb ridge presses housings down, not individual wires.
      translate([gpio_cx,gpio_cy,gpio_connector_top-0.1])
        cube([gpio_body_x,3,2.0],center=true);
    }
    for(x=[gpio_cx-gpio_body_x/2-5,gpio_cx+gpio_body_x/2+5])
      translate([x,pi_y/2+6,gpio_connector_top-2])
        cylinder(d=m3_clearance,h=7);
  }
}

module camera_wire_clamp() {
  // Independent strain relief at the camera end for both cable systems.
  difference() {
    translate([0,camera_rear_y-4,channel_floor_z+9.2])
      cube([camera_box_x-12,5,2.4],center=true);
    // GPIO bundle saddle.
    translate([gpio_lane_center_x,camera_rear_y-4,channel_floor_z+7])
      rotate([90,0,0]) cylinder(d=6,h=7,center=true);
    // Wide, shallow CSI saddle distributes load without creasing the ribbon.
    translate([csi_lane_center_x,camera_rear_y-4,channel_floor_z+7.8])
      cube([rgb_ribbon_w+2*slip,7,2.2],center=true);
    for(x=[-camera_box_x/2+6,camera_box_x/2-6])
      translate([x,camera_rear_y-4,channel_floor_z+7])
        cylinder(d=m3_clearance,h=6);
  }
}

module thermal_coupon() {
  difference() {
    rounded(max(cam_module_x,cam_module_y)+10,
            max(cam_module_x,cam_module_y)+10,
            camera_face_t+3,2);
    translate([0,0,camera_face_t])
      cube([cam_module_x+2*slip,cam_module_y+2*slip,8],center=true);
    translate([0,0,-eps])
      cylinder(d=thermal_aperture_d,h=camera_face_t+4);
  }
}

module rgb_coupon() {
  difference() {
    rounded(rgb_pcb_x+8,rgb_pcb_y+8,rgb_total_depth+4,2);
    translate([0,0,rgb_total_depth+1])
      cube([rgb_pcb_x+2*slip,rgb_pcb_y+2*slip,8],center=true);
    translate([rgb_lens_x-rgb_pcb_x/2,
               rgb_lens_y-rgb_pcb_y/2,-eps])
      cylinder(d=rgb_aperture_d,h=rgb_total_depth+5);
  }
}

module assembly() {
  color("DimGray") base();
  color("DimGray") camera_saddle();
  color("SaddleBrown")
    translate([0,(camera_front_y+camera_rear_y)/2,0]) pitch_wedge(0);
  color("DarkSlateGray") camera_pod();
  color("SlateGray") pi_lid();
  color("Gray") fan_cap();
  color("DarkSlateGray") camera_lid();
  color("Black") channel_cover();
  color("Orange") gpio_clamp();
  color("Orange") camera_wire_clamp();
}
if(PART=="base") base();
else if(PART=="camera_saddle") camera_saddle();
else if(PART=="camera_pod") camera_pod();
else if(PART=="pi_lid") pi_lid();
else if(PART=="fan_cap") fan_cap();
else if(PART=="camera_lid") camera_lid();
else if(PART=="channel_cover") channel_cover();
else if(PART=="gpio_clamp") gpio_clamp();
else if(PART=="camera_wire_clamp") camera_wire_clamp();
else if(PART=="pitch_wedge_0") pitch_wedge(0);
else if(PART=="pitch_wedge_10") pitch_wedge(10);
else if(PART=="pitch_wedge_20") pitch_wedge(20);
else if(PART=="pitch_wedge_25") pitch_wedge(25);
else if(PART=="thermal_coupon") thermal_coupon();
else if(PART=="rgb_coupon") rgb_coupon();
else assembly();
