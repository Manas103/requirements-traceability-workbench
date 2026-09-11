"""Seed content for a SIMULATED contrast delivery (medical injector) system.

Everything in this file is invented for this project. It is not a real
Bracco, ACIST, Bayer, or any other vendor's product, requirement set, or
test plan. Any resemblance to a real device's requirement wording is
coincidental; the point is to exercise a traceability tool with content
that reads like a real infusion/injector system would, not to describe
one.

Structure: 14 user needs. Each user need has 3-4 top-level ("L1") system
requirements. Some L1 requirements decompose further into "L2" subsystem
requirements. Every node (L1 and L2) carries a short `keyword` tag used
later to check whether a linked test actually exercises the requirement
it claims to verify (see reports.py).

Node tuple shape: (key, text, keyword, [child_node, ...])
"""

USER_NEEDS = [
    ("un_needle", "As a clinician, I need the injector's needle interface to minimize risk of "
                  "needle-stick injury and misinsertion during contrast administration."),
    ("un_catheter", "As a clinician, I need a secure, leak-free connection between the injector "
                    "syringe and the patient catheter line."),
    ("un_flow", "As a clinician, I need the injector to deliver contrast at a precisely "
                "controlled, programmable flow rate and volume."),
    ("un_air", "As a clinician, I need the system to prevent injection of air into the "
               "patient's vasculature."),
    ("un_reservoir", "As a clinician, I need reliable tracking of contrast media inventory "
                      "and expiration status in the reservoir/syringe."),
    ("un_occlusion", "As a clinician, I need the system to detect line occlusion before it "
                      "causes patient injury or extravasation."),
    ("un_alarm", "As a clinician, I need alarms that reliably reach my attention with "
                 "appropriate priority and are distinguishable from one another."),
    ("un_ui", "As a clinician, I need a programming interface that prevents entry of "
              "clinically unsafe injection parameters."),
    ("un_power", "As a clinician, I need the injector to keep operating safely through a "
                 "mains power interruption during an injection."),
    ("un_data", "As a clinician and biomed engineer, I need a complete, tamper-evident "
                "record of every injection delivered for the patient record and audits."),
    ("un_sterilization", "As a biomed and infection-control engineer, I need reusable "
                          "components to be validated for the facility's reprocessing "
                          "procedure between patients."),
    ("un_mechanical", "As a biomed engineer, I need the injector head and console to survive "
                       "the mechanical and environmental conditions of a busy imaging suite."),
    ("un_swsafety", "As a systems engineer, I need an independent software safety monitor "
                     "that catches a runaway or hung main control loop before it can harm "
                     "the patient."),
    ("un_network", "As a biomed and IT engineer, I need the injector's network connection to "
                    "the EMR/RIS to be secure and to never block a needed injection."),
]

REQ_TREE = {
    "un_needle": [
        ("needle_gauge_range", "The system shall support single-use needles with gauge sizes "
         "from 18G to 24G for peripheral IV access.", "needle_gauge", [
            ("needle_gauge_lockout", "The injector shall reject a programmed flow rate that "
             "exceeds the maximum rate rated for the detected needle gauge.", "needle_gauge", []),
        ]),
        ("needle_shield_engagement", "The system shall provide a passive needle-shielding "
         "mechanism that engages automatically upon withdrawal.", "needle_shield", [
            ("needle_shield_selftest", "The needle-shielding mechanism shall present a visible "
             "indicator confirming it has engaged before the needle is discarded.",
             "needle_shield", []),
        ]),
        ("needle_compat_labeling", "The system shall display the compatible needle gauge range "
         "on the injector head housing.", "needle_label", [
            ("needle_label_multilang", "The compatible needle gauge label shall be provided in "
             "English and at least one additional facility-configurable language.",
             "needle_label", []),
        ]),
    ],
    "un_catheter": [
        ("luer_lock_torque", "The syringe-to-catheter connector shall be a standard luer-lock "
         "fitting rated to withstand injection pressures up to 325 psi without disconnection.",
         "luer_lock", [
            ("luer_lock_indicator", "The system shall provide a visible or tactile confirmation "
             "that the luer-lock connection is fully seated before permitting injection.",
             "luer_lock", []),
        ]),
        ("line_leak_detection", "The system shall detect a pressure drop consistent with a line "
         "disconnect or leak within 2 seconds of onset and halt injection.", "line_leak", [
            ("leak_alarm_latency", "The leak-detection alarm shall annunciate within 500 ms of "
             "leak detection.", "line_leak", []),
            ("line_leak_selftest", "The pressure sensor used for leak detection shall execute a "
             "zero-offset self-check before each injection.", "line_leak", []),
        ]),
        ("catheter_compat_matrix", "The system shall restrict programmable flow rate and "
         "pressure limits to values compatible with the catheter gauge selected by the "
         "operator.", "catheter_compat", [
            ("catheter_compat_override", "An operator override of the catheter compatibility "
             "restriction shall require a two-step confirmation and shall be logged.",
             "catheter_compat", []),
        ]),
    ],
    "un_flow": [
        ("flow_rate_accuracy", "The injector shall deliver programmed flow rate within +/-5% "
         "of setpoint across the rated range of 0.1 to 10 mL/s.", "flow_rate", [
            ("flow_rate_closed_loop", "The pump control loop shall sample the flow sensor at "
             "100 Hz and adjust motor drive within one control cycle.", "flow_rate", []),
            ("flow_rate_calibration", "The injector shall support a field flow-rate calibration "
             "procedure traceable to a certified reference volume.", "flow_rate", []),
        ]),
        ("volume_accuracy", "The injector shall deliver the programmed total volume within "
         "+/-2% for volumes between 5 and 200 mL.", "volume_delivered", [
            ("volume_accuracy_calibration", "The system shall support a field volume-accuracy "
             "verification procedure using a calibrated graduated cylinder.",
             "volume_delivered", []),
        ]),
        ("dual_syringe_sync", "For dual-syringe (contrast/saline) configurations, the system "
         "shall synchronize switchover to within 50 ms of the programmed transition point.",
         "dual_syringe", [
            ("dual_syringe_ratio", "The system shall support programmable contrast:saline "
             "mixing ratios from 100:0 to 0:100 in 10% increments.", "dual_syringe", []),
        ]),
        ("max_pressure_limit", "The injector shall enforce an operator-programmable maximum "
         "line pressure limit between 50 and 325 psi.", "max_pressure", [
            ("max_pressure_derate", "The enforced maximum pressure limit shall automatically "
             "derate by 20% when ambient temperature exceeds 30 C, per the pump's thermal "
             "rating.", "max_pressure", []),
        ]),
    ],
    "un_air": [
        ("air_sensor_detection", "The system shall detect an air column of 0.10 mL or greater "
         "in the fluid path using ultrasonic air-in-line sensing.", "air_bubble", [
            ("air_sensor_response", "Upon air detection, the system shall halt the pump motor "
             "within 100 ms.", "air_bubble", []),
            ("air_sensor_selftest", "The air-in-line sensor shall execute a power-on self-test "
             "and fault to a safe state if the self-test fails.", "air_bubble", []),
        ]),
        ("air_purge_procedure", "The system shall provide a guided air-purge priming sequence "
         "before the line is connected to the patient.", "air_purge", [
            ("air_purge_verification", "Completion of the air-purge sequence shall be verified "
             "by the air-in-line sensor reading clear before the system enables patient "
             "connection.", "air_purge", []),
        ]),
        ("air_alarm_annunciation", "The system shall annunciate a distinct audible and visual "
         "alarm pattern specific to air-in-line detection, distinguishable from occlusion "
         "alarms.", "air_bubble", []),
    ],
    "un_reservoir": [
        ("reservoir_level_sensing", "The system shall continuously monitor contrast reservoir "
         "fill level and estimate remaining deliverable volume within +/-3 mL.",
         "reservoir_level", [
            ("low_reservoir_warning", "The system shall issue a low-reservoir warning when "
             "remaining volume falls below the volume required to complete the programmed "
             "protocol.", "reservoir_level", []),
        ]),
        ("lot_expiration_tracking", "The system shall record the contrast lot number and "
         "expiration date scanned at syringe load and block injection past the expiration "
         "date.", "lot_expiration", [
            ("lot_expiration_grace", "The system shall warn, but not block, injection of "
             "contrast within 24 hours of its expiration date, and shall block outright after "
             "expiration.", "lot_expiration", []),
        ]),
        ("reservoir_barcode_scan", "The system shall verify contrast concentration and volume "
         "against a scanned barcode before enabling injection.", "reservoir_barcode", [
            ("reservoir_barcode_mismatch", "A barcode scan that does not match the previously "
             "loaded lot shall require operator re-confirmation before proceeding.",
             "reservoir_barcode", []),
        ]),
    ],
    "un_occlusion": [
        ("occlusion_pressure_threshold", "The system shall detect a line occlusion when "
         "measured pressure exceeds the operator-set occlusion threshold for more than "
         "300 ms.", "occlusion_pressure", [
            ("occlusion_threshold_range", "The occlusion pressure threshold shall be "
             "programmable from 10 to 300 psi in 5 psi increments.", "occlusion_pressure", []),
            ("occlusion_response_halt", "Upon occlusion detection, the pump shall halt motor "
             "drive within 200 ms and hold the last commanded position.", "occlusion_pressure",
             []),
        ]),
        ("extravasation_pattern_detect", "The system shall flag a suspected extravasation "
         "pattern when pressure rises gradually without reaching the hard occlusion "
         "threshold, using a slope-based heuristic.", "extravasation", [
            ("extravasation_operator_alert", "A suspected extravasation pattern shall present "
             "a distinct on-screen advisory recommending clinical assessment, separate from "
             "the hard occlusion alarm.", "extravasation", []),
        ]),
        ("occlusion_alarm_priority", "Occlusion alarms shall be assigned the highest "
         "annunciation priority level in the alarm system, per IEC 60601-1-8 style "
         "prioritization.", "occlusion_pressure", []),
    ],
    "un_alarm": [
        ("alarm_priority_levels", "The system shall implement three alarm priority levels "
         "(high, medium, low) each with a distinct audible pattern per IEC 60601-1-8.",
         "alarm_priority", [
            ("alarm_visual_coding", "Each alarm priority level shall be paired with a distinct "
             "visual indicator color (red, yellow, cyan).", "alarm_priority", []),
        ]),
        ("alarm_silence_timeout", "An operator-initiated alarm silence shall time out and "
         "re-annunciate after no more than 120 seconds if the underlying condition "
         "persists.", "alarm_silence", [
            ("alarm_silence_max_duration", "The maximum single silence duration for a "
             "high-priority alarm shall not exceed 2 minutes, per IEC 60601-1-8.",
             "alarm_silence", []),
        ]),
        ("alarm_log_retention", "The system shall retain the most recent 500 alarm events in "
         "non-volatile storage with timestamp and acknowledgment record.", "alarm_log", [
            ("alarm_log_export", "The system shall support exporting the alarm log in a "
             "structured, human-readable format for service review.", "alarm_log", []),
        ]),
    ],
    "un_ui": [
        ("param_range_validation", "The user interface shall reject entry of a flow rate, "
         "volume, or pressure limit outside the clinically validated range for the selected "
         "protocol.", "param_validation", [
            ("param_confirm_dialog", "The user interface shall require a second, explicit "
             "confirmation before accepting a programmed parameter that exceeds a soft "
             "warning threshold.", "param_validation", []),
        ]),
        ("protocol_library", "The system shall provide a library of at least 10 preconfigured "
         "injection protocols selectable by exam type.", "protocol_library", [
            ("protocol_library_custom", "The system shall allow a site administrator to add up "
             "to 20 custom protocols to the library, subject to the same range validation as "
             "built-in protocols.", "protocol_library", []),
        ]),
        ("ui_lockout_cleaning", "The user interface shall lock out parameter entry while the "
         "system reports an active cleaning or reprocessing cycle.", "ui_lockout", [
            ("ui_lockout_override", "A supervisor override of the cleaning-cycle lockout shall "
             "require a service PIN and shall be logged.", "ui_lockout", []),
        ]),
    ],
    "un_power": [
        ("battery_backup_runtime", "The system shall provide battery backup capable of "
         "completing an in-progress injection and safely parking the pump for at least 5 "
         "minutes after loss of mains power.", "battery_backup", [
            ("battery_health_monitor", "The system shall monitor battery state of health and "
             "issue a service alert when capacity falls below 80% of rated.",
             "battery_backup", []),
        ]),
        ("power_loss_state_preserve", "Upon mains power loss, the system shall preserve the "
         "in-progress protocol state and resume without requiring re-programming once power "
         "is restored.", "power_loss", []),
        ("ground_fault_protection", "The system shall detect a ground fault condition on the "
         "patient-connected circuit and disconnect within the time limits of IEC 60601-1.",
         "ground_fault", [
            ("ground_fault_selftest", "Ground fault protection circuitry shall be exercised by "
             "a self-test at power-on.", "ground_fault", []),
        ]),
    ],
    "un_data": [
        ("injection_record_completeness", "The system shall record programmed and "
         "actually-delivered flow rate, volume, and pressure profile for every injection.",
         "injection_record", [
            ("injection_record_integrity", "Each injection record shall include a checksum to "
             "detect post-hoc tampering.", "injection_record", []),
            ("injection_record_export", "The system shall support exporting injection records "
             "in a structured format for integration with the hospital information system.",
             "injection_record", []),
        ]),
        ("audit_trail_user_actions", "The system shall log operator identity and timestamp for "
         "every parameter change, in a separate append-only audit trail.", "audit_trail", [
            ("audit_trail_retention", "The audit trail shall retain at least 2 years of "
             "operator action records before the oldest records may be archived.",
             "audit_trail", []),
        ]),
        ("clock_sync_ntp", "The system shall synchronize its internal clock to facility "
         "network time within +/-1 second when connected to the network.", "clock_sync", [
            ("clock_sync_fallback", "If network time is unavailable, the system shall fall "
             "back to its internal real-time clock and flag records with a reduced-confidence "
             "timestamp source.", "clock_sync", []),
        ]),
    ],
    "un_sterilization": [
        ("reprocessing_cycle_validation", "Reusable fluid-path components shall be validated "
         "to withstand the facility's specified high-level disinfection cycle for a minimum "
         "of 100 cycles.", "reprocessing", [
            ("reprocessing_cycle_count_display", "The system shall display the remaining "
             "validated reprocessing cycle count for a reusable component that reports a "
             "use-counter.", "reprocessing", []),
        ]),
        ("single_use_component_lockout", "The system shall detect an already-used single-use "
         "syringe or tubing set, via an embedded use-counter chip, and prevent reuse.",
         "single_use_lockout", [
            ("single_use_lockout_override", "An override of the single-use lockout shall "
             "require a documented service-level authorization code, logged in the audit "
             "trail.", "single_use_lockout", []),
        ]),
        ("housing_material_disinfectant", "External housing materials shall be compatible "
         "with the facility's list of approved surface disinfectants without degradation "
         "over 500 wipe cycles.", "housing_material", []),
    ],
    "un_mechanical": [
        ("ip_rating_fluid_ingress", "The injector head shall meet at least IP34 fluid-ingress "
         "protection to tolerate incidental contrast spillage.", "ip_rating", []),
        ("emc_immunity", "The system shall meet IEC 60601-1-2 electromagnetic immunity "
         "requirements for use adjacent to CT and angiography equipment.", "emc_immunity", [
            ("emc_mri_conditional", "If offered in an MRI-conditional configuration, the "
             "system shall be labeled per ASTM F2503 MRI conditional labeling "
             "requirements.", "emc_immunity", []),
        ]),
        ("drop_shock_rating", "The mobile console shall withstand a 75 cm drop onto a hard "
         "floor on any face without loss of basic safety function.", "drop_shock", []),
        ("caster_brake_stability", "The mobile console shall not tip over when the loaded "
         "injector head arm is extended to its maximum reach at any caster-locked "
         "orientation.", "caster_stability", [
            ("caster_lock_indicator", "The system shall provide a visible indicator of "
             "caster-lock engagement state.", "caster_stability", []),
        ]),
    ],
    "un_swsafety": [
        ("watchdog_timer_reset", "An independent hardware watchdog timer shall force a "
         "safe-state stop if the main control loop fails to service it within 250 ms.",
         "watchdog", [
            ("watchdog_selftest_poweron", "The watchdog circuit shall be exercised as part of "
             "power-on self-test before the system is placed in a ready state.", "watchdog",
             []),
        ]),
        ("dual_channel_pressure_check", "Line pressure shall be independently measured by two "
         "physically separate sensors, and injection shall halt if the two readings disagree "
         "by more than 15%.", "dual_channel", []),
        ("software_version_integrity", "The system shall verify a cryptographic signature on "
         "the control software image at boot and refuse to run an unsigned or modified "
         "image.", "sw_integrity", [
            ("sw_update_rollback", "A failed software update shall automatically roll back to "
             "the last known-good verified image.", "sw_integrity", []),
        ]),
        ("safe_state_definition", "Following any detected fault, the system shall enter a "
         "defined safe state, motor de-energized, valve closed, alarm active, within 500 ms.",
         "safe_state", []),
    ],
    "un_network": [
        ("network_isolation_degrade", "Loss of network connectivity to the EMR/RIS shall not "
         "prevent the system from delivering a locally-programmed injection.",
         "network_isolation", []),
        ("emr_worklist_integrity", "Patient worklist data received from the EMR shall be "
         "validated, patient ID and exam type, against the operator's manual entry before an "
         "injection is enabled.", "emr_worklist", [
            ("emr_data_encryption", "Data exchanged with the EMR/RIS over the network shall be "
             "encrypted in transit using TLS 1.2 or higher.", "emr_worklist", []),
        ]),
        ("remote_service_access_auth", "Remote service access to the injector's diagnostic "
         "interface shall require multi-factor authentication and shall be logged.",
         "remote_access", [
            ("remote_access_session_timeout", "A remote service session shall automatically "
             "terminate after 15 minutes of inactivity.", "remote_access", []),
        ]),
    ],
}


def count_requirements():
    total = 0
    for nodes in REQ_TREE.values():
        total += _count_nodes(nodes)
    return total


def _count_nodes(nodes):
    n = 0
    for _key, _text, _kw, children in nodes:
        n += 1
        n += _count_nodes(children)
    return n


if __name__ == "__main__":
    print("user needs:", len(USER_NEEDS))
    print("requirements:", count_requirements())
