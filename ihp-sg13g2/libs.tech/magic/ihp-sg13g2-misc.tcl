#----------------------------------------------------------------

proc sg13g2::subconn_draw {} {
   set w [magic::i2u [box width]]
   set h [magic::i2u [box height]]
   if {$w < 0.16} {
      puts stderr "Substrate tap width must be at least 0.16um"
      return
   }
   if {$h < 0.16} {
      puts stderr "Substrate tap height must be at least 0.16um"
      return
   }
   suspendall
   paint psc
   pushbox
   if {$w > $h} {
      box grow e 0.05um
      box grow w 0.05um
      paint m1
      box grow e 0.02um
      box grow w 0.02um
   } else {
      box grow n 0.05um
      box grow s 0.05um
      paint m1
      box grow n 0.02um
      box grow s 0.02um
   }
   paint psd
   popbox
   resumeall
}

#----------------------------------------------------------------

proc sg13g2::hvsubconn_draw {} {
   set w [magic::i2u [box width]]
   set h [magic::i2u [box height]]
   if {$w < 0.16} {
      puts stderr "Substrate tap width must be at least 0.16um"
      return
   }
   if {$h < 0.16} {
      puts stderr "Substrate tap height must be at least 0.16um"
      return
   }
   suspendall
   paint hvpsc
   pushbox
   if {$w > $h} {
      box grow e 0.05um
      box grow w 0.05um
      paint m1
      box grow e 0.02um
      box grow w 0.02um
   } else {
      box grow n 0.05um
      box grow s 0.05um
      paint m1
      box grow n 0.02um
      box grow s 0.02um
   }
   paint hvpsd
   popbox
   resumeall
}

#----------------------------------------------------------------
# Helper function for drawing guard rings.
# Assumes that a box exists and defines the centerlines of the
# guard ring contacts.
# ctype = type to paint for contact
# dtype = type to paint for diffusion
#----------------------------------------------------------------

proc sg13g2::guard_ring_draw {ctype dtype} {
   pushbox
   box width 0
   box grow c 0.08um
   paint m1
   pushbox
   box grow n -0.3um
   box grow s -0.3um
   paint $ctype
   popbox
   box grow c 0.07um
   paint $dtype
   popbox

   pushbox
   box height 0
   box grow c 0.08um
   paint m1
   pushbox
   box grow e -0.3um
   box grow w -0.3um
   paint $ctype
   popbox
   box grow c 0.07um
   paint $dtype
   popbox

   pushbox
   box move n [box height]i
   box height 0
   box grow c 0.08um
   paint m1
   pushbox
   box grow e -0.3um
   box grow w -0.3um
   paint $ctype
   popbox
   box grow c 0.07um
   paint $dtype
   popbox

   pushbox
   box move e [box width]i
   box width 0
   box grow c 0.08um
   paint m1
   pushbox
   box grow n -0.3um
   box grow s -0.3um
   paint $ctype
   popbox
   box grow c 0.07um
   paint $dtype
   popbox
}

#----------------------------------------------------------------

proc sg13g2::subconn_guard_draw {} {
   set w [magic::i2u [box width]]
   set h [magic::i2u [box height]]
   # NOTE:  Width and height are determined by the requirement for
   # a contact on each side.  There is not much that can be done
   # with an guarded nwell smaller than that, anyway.
   if {$w < 0.6} {
      puts stderr "Substrate guard ring width must be at least 0.6um"
      return
   }
   if {$h < 0.6} {
      puts stderr "Substrate guard ring height must be at least 0.6um"
      return
   }
   suspendall
   tech unlock *
   pushbox

   sg13g2::guard_ring_draw psc psd

   popbox
   tech revert
   resumeall
}

#----------------------------------------------------------------

proc sg13g2::hvsubconn_guard_draw {} {
   set w [magic::i2u [box width]]
   set h [magic::i2u [box height]]
   # NOTE:  Width and height are determined by the requirement for
   # a contact on each side.  There is not much that can be done
   # with an guarded nwell smaller than that, anyway.
   if {$w < 0.6} {
      puts stderr "Substrate guard ring width must be at least 0.6um"
      return
   }
   if {$h < 0.6} {
      puts stderr "Substrate guard ring height must be at least 0.6um"
      return
   }
   suspendall
   tech unlock *
   pushbox

   sg13g2::guard_ring_draw hvpsc hvpsd

   popbox
   tech revert
   resumeall
}

#----------------------------------------------------------------

proc sg13g2::nwell_draw {} {
   set w [magic::i2u [box width]]
   set h [magic::i2u [box height]]
   # NOTE:  Width and height are determined by the requirement for
   # a contact on each side.  There is not much that can be done
   # with an guarded nwell smaller than that, anyway.
   if {$w < 0.62} {
      puts stderr "N-well region width must be at least 0.62um"
      return
   }
   if {$h < 0.62} {
      puts stderr "N-well region height must be at least 0.62um"
      return
   }
   suspendall
   tech unlock *
   pushbox
   pushbox
   box grow c 0.265um
   paint nwell
   popbox

   sg13g2::guard_ring_draw nsc nsd

   popbox
   tech revert
   resumeall
}

#----------------------------------------------------------------

proc sg13g2::hvnwell_draw {} {
   set w [magic::i2u [box width]]
   set h [magic::i2u [box height]]
   # NOTE:  Width and height are determined by the requirement for
   # a contact on each side.  There is not much that can be done
   # with an guarded nwell smaller than that, anyway.
   if {$w < 0.62} {
      puts stderr "MV N-well region width must be at least 0.62um"
      return
   }
   if {$h < 0.62} {
      puts stderr "MV N-well region height must be at least 0.26um"
      return
   }
   suspendall
   tech unlock *
   pushbox
   pushbox
   box grow c 0.415um
   paint nwell
   popbox

   sg13g2::guard_ring_draw hvnsc hvnsd

   popbox
   tech revert
   resumeall
}

#----------------------------------------------------------------

proc sg13g2::deep_nwell_draw {} {
   set w [magic::i2u [box width]]
   set h [magic::i2u [box height]]
   if {$w < 3.0} {
      puts stderr "Deep-nwell region width must be at least 3.0um"
      return
   }
   if {$h < 3.0} {
      puts stderr "Deep-nwell region height must be at least 3.0um"
      return
   }
   suspendall
   tech unlock *
   paint dnwell
   pushbox
   pushbox
   box grow c 0.4um
   # Note:  Previous implementation was to draw nwell over the whole
   # area and then erase it from the center.  That can interact with
   # any layout already drawn in the center area.  Instead, draw four
   # separate rectangles.
   # -----------------
   # paint nwell
   # box grow c -1.05um
   # erase nwell
   # -----------------
   pushbox
   box width 1.05um
   paint nwell
   popbox
   pushbox
   box height 1.05um
   paint nwell
   popbox
   pushbox
   box move n ${h}um
   box move n 0.8um
   box move s 1.05um
   box height 1.05um
   paint nwell
   popbox
   pushbox
   box move e ${w}um
   box move e 0.8um
   box move w 1.05um
   box width 1.05um
   paint nwell
   popbox

   popbox
   box grow c 0.03um

   pushbox
   box width 0
   box grow c 0.085um
   paint m1
   pushbox
   box grow n -0.3um
   box grow s -0.3um
   paint nsc
   popbox
   box grow c 0.1um
   paint nsd
   popbox

   pushbox
   box height 0
   box grow c 0.085um
   paint m1
   pushbox
   box grow e -0.3um
   box grow w -0.3um
   paint nsc
   popbox
   box grow c 0.1um
   paint nsd
   popbox

   pushbox
   box move n [box height]i
   box height 0
   box grow c 0.085um
   paint m1
   pushbox
   box grow e -0.3um
   box grow w -0.3um
   paint nsc
   popbox
   box grow c 0.1um
   paint nsd
   popbox

   pushbox
   box move e [box width]i
   box width 0
   box grow c 0.085um
   paint m1
   pushbox
   box grow n -0.3um
   box grow s -0.3um
   paint nsc
   box grow c 0.1um
   paint nsd
   popbox

   popbox
   tech revert
   resumeall
}

#----------------------------------------------------------------

proc sg13g2::hvdeep_nwell_draw {} {
   set w [magic::i2u [box width]]
   set h [magic::i2u [box height]]
   if {$w < 3.0} {
      puts stderr "MV Deep-nwell region width must be at least 3.0um"
      return
   }
   if {$h < 3.0} {
      puts stderr "MV Deep-nwell region height must be at least 3.0um"
      return
   }
   suspendall
   tech unlock *
   paint dnwell
   pushbox
   pushbox
   box grow c 0.55um
   pushbox
   box width 1.58um
   paint nwell
   popbox
   pushbox
   box height 1.58um
   paint nwell
   popbox
   pushbox
   box move n ${h}um
   box move n 1.1um
   box move s 1.58um
   box height 1.58um
   paint nwell
   popbox
   pushbox
   box move e ${w}um
   box move e 1.1um
   box move w 1.58um
   box width 1.58um
   paint nwell
   popbox

   popbox
   box grow c 0.03um

   pushbox
   box width 0
   box grow c 0.085um
   paint m1
   pushbox
   box grow n -0.3um
   box grow s -0.3um
   paint hvnsc
   popbox
   box grow c 0.1um
   paint hvnsd
   popbox

   pushbox
   box height 0
   box grow c 0.085um
   paint m1
   pushbox
   box grow e -0.3um
   box grow w -0.3um
   paint hvnsc
   popbox
   box grow c 0.1um
   paint hvnsd
   popbox

   pushbox
   box move n [box height]i
   box height 0
   box grow c 0.085um
   paint m1
   pushbox
   box grow e -0.3um
   box grow w -0.3um
   paint hvnsc
   popbox
   box grow c 0.1um
   paint hvnsd
   popbox

   pushbox
   box move e [box width]i
   box width 0
   box grow c 0.085um
   paint m1
   pushbox
   box grow n -0.3um
   box grow s -0.3um
   paint hvnsc
   box grow c 0.1um
   paint hvnsd
   popbox

   popbox
   tech revert
   resumeall
}

#----------------------------------------------------------------
