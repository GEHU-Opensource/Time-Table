import pandas as pd

# Suppose your JSON-like data is stored in a variable called 'timetable'
timetable = {
    "Monday": {
        "A": [
            {
                "teacher_id": "AP24",
                "subject_id": "SCS-501",
                "classroom_id": "R1",
                "time_slot": "08:00 - 09:00",
                "group": "all"
            },
            {
                "teacher_id": "SJ16",
                "subject_id": "TCS-509",
                "classroom_id": "R1",
                "time_slot": "09:00 - 10:00",
                "group": "all"
            },
            {
                "teacher_id": "PM14",
                "subject_id": "PMA-502",
                "classroom_id": "L1",
                "time_slot": "11:00 - 12:00",
                "group": "all"
            },
            {
                "teacher_id": "BJ10",
                "subject_id": "TMA-502",
                "classroom_id": "R1",
                "time_slot": "12:00 - 13:00",
                "group": "all"
            }
        ],
        "B": [
            {
                "teacher_id": "SP06",
                "subject_id": "TCS-503",
                "classroom_id": "R2",
                "time_slot": "08:00 - 09:00",
                "group": "all"
            },
            {
                "teacher_id": "AB17",
                "subject_id": "TCS-509",
                "classroom_id": "R2",
                "time_slot": "09:00 - 10:00",
                "group": "all"
            },
            {
                "teacher_id": "AB01",
                "subject_id": "TCS-531",
                "classroom_id": "R2",
                "time_slot": "11:00 - 12:00",
                "group": "all"
            },
            {
                "teacher_id": "RS11",
                "subject_id": "TMA-502",
                "classroom_id": "R2",
                "time_slot": "12:00 - 13:00",
                "group": "all"
            }
        ],
        "C": [
            {
                "teacher_id": "DP07",
                "subject_id": "TCS-503",
                "classroom_id": "R3",
                "time_slot": "08:00 - 09:00",
                "group": "all"
            },
            {
                "teacher_id": "HP18",
                "subject_id": "TCS-509",
                "classroom_id": "R3",
                "time_slot": "09:00 - 10:00",
                "group": "all"
            },
            {
                "teacher_id": "VD25",
                "subject_id": "PCS-503",
                "classroom_id": "L1",
                "time_slot": "11:00 - 12:00",
                "group": "all"
            },
            {
                "teacher_id": "PK02",
                "subject_id": "TCS-531",
                "classroom_id": "R3",
                "time_slot": "12:00 - 13:00",
                "group": "all"
            }
        ],
        "D": [
            {
                "teacher_id": "DT20",
                "subject_id": "XCS-501",
                "classroom_id": "R4",
                "time_slot": "08:00 - 09:00",
                "group": "all"
            },
            {
                "teacher_id": "SG19",
                "subject_id": "TCS-509",
                "classroom_id": "R4",
                "time_slot": "09:00 - 10:00",
                "group": "all"
            },
            {
                "teacher_id": "AD08",
                "subject_id": "PMA-502",
                "classroom_id": "L2",
                "time_slot": "11:00 - 12:00",
                "group": "all"
            },
            {
                "teacher_id": "AD08",
                "subject_id": "PMA-502",
                "classroom_id": "L2",
                "time_slot": "12:00 - 13:00",
                "group": "all"
            },
            {
                "teacher_id": "DP07",
                "subject_id": "PCS-503",
                "classroom_id": "L2",
                "time_slot": "13:50 - 14:50",
                "group": "all"
            },
            {
                "teacher_id": "DP07",
                "subject_id": "PCS-503",
                "classroom_id": "L2",
                "time_slot": "14:50 - 15:50",
                "group": "all"
            },
            {
                "teacher_id": "AP24",
                "subject_id": "SCS-501",
                "classroom_id": "R4",
                "time_slot": "16:50 - 17:50",
                "group": "all"
            }
        ],
        "E": [
            {
                "teacher_id": "SS03",
                "subject_id": "TCS-502",
                "classroom_id": "R5",
                "time_slot": "08:00 - 09:00",
                "group": "all"
            },
            {
                "teacher_id": "PA21",
                "subject_id": "XCS-501",
                "classroom_id": "R5",
                "time_slot": "09:00 - 10:00",
                "group": "all"
            },
            {
                "teacher_id": "SP06",
                "subject_id": "PCS-503",
                "classroom_id": "L2",
                "time_slot": "11:00 - 12:00",
                "group": "all"
            },
            {
                "teacher_id": "SP06",
                "subject_id": "PCS-503",
                "classroom_id": "L2",
                "time_slot": "12:00 - 13:00",
                "group": "all"
            },
            {
                "teacher_id": "RD09",
                "subject_id": "PCS-506",
                "classroom_id": "L1",
                "time_slot": "13:50 - 14:50",
                "group": "all"
            },
            {
                "teacher_id": "RD09",
                "subject_id": "PCS-506",
                "classroom_id": "L1",
                "time_slot": "14:50 - 15:50",
                "group": "all"
            },
            {
                "teacher_id": "SJ16",
                "subject_id": "TCS-509",
                "classroom_id": "R5",
                "time_slot": "16:50 - 17:50",
                "group": "all"
            }
        ],
        "F": [
            {
                "teacher_id": "RS11",
                "subject_id": "PCS-503",
                "classroom_id": "L2",
                "time_slot": "08:00 - 09:00",
                "group": "all"
            },
            {
                "teacher_id": "AK23",
                "subject_id": "CSP-501",
                "classroom_id": "R6",
                "time_slot": "09:00 - 10:00",
                "group": "all"
            },
            {
                "teacher_id": "AD08",
                "subject_id": "PCS-506",
                "classroom_id": "L1",
                "time_slot": "11:00 - 12:00",
                "group": "all"
            },
            {
                "teacher_id": "AD08",
                "subject_id": "PCS-506",
                "classroom_id": "L1",
                "time_slot": "12:00 - 13:00",
                "group": "all"
            },
            {
                "teacher_id": "RD09",
                "subject_id": "PCS-506",
                "classroom_id": "L1",
                "time_slot": "13:50 - 14:50",
                "group": "all"
            },
            {
                "teacher_id": "RD09",
                "subject_id": "PCS-506",
                "classroom_id": "L1",
                "time_slot": "14:50 - 15:50",
                "group": "all"
            },
            {
                "teacher_id": "AB01",
                "subject_id": "TCS-531",
                "classroom_id": "R6",
                "time_slot": "16:50 - 17:50",
                "group": "all"
            }
        ]
    },
    "Tuesday": {
        "A": [
            {
                "teacher_id": "SS03",
                "subject_id": "TCS-502",
                "classroom_id": "R1",
                "time_slot": "08:00 - 09:00",
                "group": "all"
            },
            {
                "teacher_id": "SP06",
                "subject_id": "TCS-503",
                "classroom_id": "R1",
                "time_slot": "09:00 - 10:00",
                "group": "all"
            },
            {
                "teacher_id": "AB01",
                "subject_id": "TCS-531",
                "classroom_id": "R1",
                "time_slot": "11:00 - 12:00",
                "group": "all"
            },
            {
                "teacher_id": "SJ16",
                "subject_id": "TCS-509",
                "classroom_id": "R1",
                "time_slot": "12:00 - 13:00",
                "group": "all"
            }
        ],
        "B": [
            {
                "teacher_id": "AK23",
                "subject_id": "CSP-501",
                "classroom_id": "R2",
                "time_slot": "08:00 - 09:00",
                "group": "all"
            },
            {
                "teacher_id": "AB17",
                "subject_id": "TCS-509",
                "classroom_id": "R2",
                "time_slot": "09:00 - 10:00",
                "group": "all"
            },
            {
                "teacher_id": "DT20",
                "subject_id": "XCS-501",
                "classroom_id": "R2",
                "time_slot": "11:00 - 12:00",
                "group": "all"
            },
            {
                "teacher_id": "DP07",
                "subject_id": "TCS-503",
                "classroom_id": "R2",
                "time_slot": "12:00 - 13:00",
                "group": "all"
            }
        ],
        "C": [
            {
                "teacher_id": "BJ10",
                "subject_id": "TMA-502",
                "classroom_id": "R3",
                "time_slot": "08:00 - 09:00",
                "group": "all"
            },
            {
                "teacher_id": "HP18",
                "subject_id": "TCS-509",
                "classroom_id": "R3",
                "time_slot": "09:00 - 10:00",
                "group": "all"
            },
            {
                "teacher_id": "AA04",
                "subject_id": "TCS-502",
                "classroom_id": "R3",
                "time_slot": "11:00 - 12:00",
                "group": "all"
            },
            {
                "teacher_id": "PA21",
                "subject_id": "XCS-501",
                "classroom_id": "R3",
                "time_slot": "12:00 - 13:00",
                "group": "all"
            }
        ],
        "D": [
            {
                "teacher_id": "SG19",
                "subject_id": "TCS-509",
                "classroom_id": "R4",
                "time_slot": "08:00 - 09:00",
                "group": "all"
            },
            {
                "teacher_id": "AK23",
                "subject_id": "CSP-501",
                "classroom_id": "R4",
                "time_slot": "09:00 - 10:00",
                "group": "all"
            },
            {
                "teacher_id": "RD09",
                "subject_id": "PCS-506",
                "classroom_id": "L1",
                "time_slot": "11:00 - 12:00",
                "group": "all"
            },
            {
                "teacher_id": "RD09",
                "subject_id": "PCS-506",
                "classroom_id": "L1",
                "time_slot": "12:00 - 13:00",
                "group": "all"
            },
            {
                "teacher_id": "AD08",
                "subject_id": "PCS-506",
                "classroom_id": "L2",
                "time_slot": "13:50 - 14:50",
                "group": "all"
            },
            {
                "teacher_id": "AD08",
                "subject_id": "PCS-506",
                "classroom_id": "L2",
                "time_slot": "14:50 - 15:50",
                "group": "all"
            },
            {
                "teacher_id": "NB22",
                "subject_id": "XCS-501",
                "classroom_id": "R4",
                "time_slot": "16:50 - 17:50",
                "group": "all"
            }
        ],
        "E": [
            {
                "teacher_id": "PM14",
                "subject_id": "PMA-502",
                "classroom_id": "L2",
                "time_slot": "08:00 - 09:00",
                "group": "all"
            },
            {
                "teacher_id": "AC05",
                "subject_id": "TCS-502",
                "classroom_id": "R5",
                "time_slot": "09:00 - 10:00",
                "group": "all"
            },
            {
                "teacher_id": "SP06",
                "subject_id": "PCS-503",
                "classroom_id": "L1",
                "time_slot": "11:00 - 12:00",
                "group": "all"
            },
            {
                "teacher_id": "SP06",
                "subject_id": "PCS-503",
                "classroom_id": "L1",
                "time_slot": "12:00 - 13:00",
                "group": "all"
            },
            {
                "teacher_id": "RS11",
                "subject_id": "PCS-503",
                "classroom_id": "L2",
                "time_slot": "13:50 - 14:50",
                "group": "all"
            },
            {
                "teacher_id": "RS11",
                "subject_id": "PCS-503",
                "classroom_id": "L2",
                "time_slot": "14:50 - 15:50",
                "group": "all"
            },
            {
                "teacher_id": "AK23",
                "subject_id": "CSP-501",
                "classroom_id": "R5",
                "time_slot": "16:50 - 17:50",
                "group": "all"
            }
        ],
        "F": [
            {
                "teacher_id": "PK02",
                "subject_id": "TCS-531",
                "classroom_id": "R6",
                "time_slot": "08:00 - 09:00",
                "group": "all"
            },
            {
                "teacher_id": "AP24",
                "subject_id": "SCS-501",
                "classroom_id": "R6",
                "time_slot": "09:00 - 10:00",
                "group": "all"
            },
            {
                "teacher_id": "DP07",
                "subject_id": "PCS-503",
                "classroom_id": "L1",
                "time_slot": "11:00 - 12:00",
                "group": "all"
            },
            {
                "teacher_id": "DP07",
                "subject_id": "PCS-503",
                "classroom_id": "L1",
                "time_slot": "12:00 - 13:00",
                "group": "all"
            },
            {
                "teacher_id": "VD25",
                "subject_id": "PCS-503",
                "classroom_id": "L1",
                "time_slot": "13:50 - 14:50",
                "group": "all"
            },
            {
                "teacher_id": "VD25",
                "subject_id": "PCS-503",
                "classroom_id": "L1",
                "time_slot": "14:50 - 15:50",
                "group": "all"
            },
            {
                "teacher_id": "SP06",
                "subject_id": "TCS-503",
                "classroom_id": "R6",
                "time_slot": "16:50 - 17:50",
                "group": "all"
            }
        ]
    },
    "Wednesday": {
        "A": [
            {
                "teacher_id": "AB01",
                "subject_id": "TCS-531",
                "classroom_id": "R1",
                "time_slot": "08:00 - 09:00",
                "group": "all"
            },
            {
                "teacher_id": "AK23",
                "subject_id": "CSP-501",
                "classroom_id": "R1",
                "time_slot": "09:00 - 10:00",
                "group": "all"
            },
            {
                "teacher_id": "DT20",
                "subject_id": "XCS-501",
                "classroom_id": "R1",
                "time_slot": "11:00 - 12:00",
                "group": "all"
            },
            {
                "teacher_id": "SP06",
                "subject_id": "TCS-503",
                "classroom_id": "R1",
                "time_slot": "12:00 - 13:00",
                "group": "all"
            }
        ],
        "B": [
            {
                "teacher_id": "AD08",
                "subject_id": "PCS-506",
                "classroom_id": "L2",
                "time_slot": "08:00 - 09:00",
                "group": "all"
            },
            {
                "teacher_id": "PA21",
                "subject_id": "XCS-501",
                "classroom_id": "R2",
                "time_slot": "09:00 - 10:00",
                "group": "all"
            },
            {
                "teacher_id": "RS11",
                "subject_id": "PCS-503",
                "classroom_id": "L1",
                "time_slot": "11:00 - 12:00",
                "group": "all"
            },
            {
                "teacher_id": "BJ10",
                "subject_id": "TMA-502",
                "classroom_id": "R2",
                "time_slot": "12:00 - 13:00",
                "group": "all"
            }
        ],
        "C": [
            {
                "teacher_id": "JM12",
                "subject_id": "TMA-502",
                "classroom_id": "R3",
                "time_slot": "08:00 - 09:00",
                "group": "all"
            },
            {
                "teacher_id": "SJ16",
                "subject_id": "TCS-509",
                "classroom_id": "R3",
                "time_slot": "09:00 - 10:00",
                "group": "all"
            },
            {
                "teacher_id": "AK23",
                "subject_id": "CSP-501",
                "classroom_id": "R3",
                "time_slot": "11:00 - 12:00",
                "group": "all"
            },
            {
                "teacher_id": "NB22",
                "subject_id": "XCS-501",
                "classroom_id": "R3",
                "time_slot": "12:00 - 13:00",
                "group": "all"
            }
        ],
        "D": [
            {
                "teacher_id": "NJ13",
                "subject_id": "TMA-502",
                "classroom_id": "R4",
                "time_slot": "08:00 - 09:00",
                "group": "all"
            },
            {
                "teacher_id": "DP07",
                "subject_id": "TCS-503",
                "classroom_id": "R4",
                "time_slot": "09:00 - 10:00",
                "group": "all"
            },
            {
                "teacher_id": "AD08",
                "subject_id": "PMA-502",
                "classroom_id": "L2",
                "time_slot": "11:00 - 12:00",
                "group": "all"
            },
            {
                "teacher_id": "AD08",
                "subject_id": "PMA-502",
                "classroom_id": "L2",
                "time_slot": "12:00 - 13:00",
                "group": "all"
            },
            {
                "teacher_id": "RD09",
                "subject_id": "PCS-506",
                "classroom_id": "L1",
                "time_slot": "13:50 - 14:50",
                "group": "all"
            },
            {
                "teacher_id": "RD09",
                "subject_id": "PCS-506",
                "classroom_id": "L1",
                "time_slot": "14:50 - 15:50",
                "group": "all"
            },
            {
                "teacher_id": "SS03",
                "subject_id": "TCS-502",
                "classroom_id": "R4",
                "time_slot": "16:50 - 17:50",
                "group": "all"
            }
        ],
        "E": [
            {
                "teacher_id": "DT20",
                "subject_id": "XCS-501",
                "classroom_id": "R5",
                "time_slot": "08:00 - 09:00",
                "group": "all"
            },
            {
                "teacher_id": "AP24",
                "subject_id": "SCS-501",
                "classroom_id": "R5",
                "time_slot": "09:00 - 10:00",
                "group": "all"
            },
            {
                "teacher_id": "AD08",
                "subject_id": "PMA-502",
                "classroom_id": "L2",
                "time_slot": "11:00 - 12:00",
                "group": "all"
            },
            {
                "teacher_id": "AD08",
                "subject_id": "PMA-502",
                "classroom_id": "L2",
                "time_slot": "12:00 - 13:00",
                "group": "all"
            },
            {
                "teacher_id": "RD09",
                "subject_id": "PCS-506",
                "classroom_id": "L1",
                "time_slot": "13:50 - 14:50",
                "group": "all"
            },
            {
                "teacher_id": "RD09",
                "subject_id": "PCS-506",
                "classroom_id": "L1",
                "time_slot": "14:50 - 15:50",
                "group": "all"
            },
            {
                "teacher_id": "PK02",
                "subject_id": "TCS-531",
                "classroom_id": "R5",
                "time_slot": "16:50 - 17:50",
                "group": "all"
            }
        ],
        "F": [
            {
                "teacher_id": "AC05",
                "subject_id": "TCS-503",
                "classroom_id": "R6",
                "time_slot": "08:00 - 09:00",
                "group": "all"
            },
            {
                "teacher_id": "AB17",
                "subject_id": "TCS-509",
                "classroom_id": "R6",
                "time_slot": "09:00 - 10:00",
                "group": "all"
            },
            {
                "teacher_id": "RS11",
                "subject_id": "PCS-503",
                "classroom_id": "L2",
                "time_slot": "11:00 - 12:00",
                "group": "all"
            },
            {
                "teacher_id": "RS11",
                "subject_id": "PCS-503",
                "classroom_id": "L2",
                "time_slot": "12:00 - 13:00",
                "group": "all"
            },
            {
                "teacher_id": "VD25",
                "subject_id": "PCS-503",
                "classroom_id": "L1",
                "time_slot": "13:50 - 14:50",
                "group": "all"
            },
            {
                "teacher_id": "VD25",
                "subject_id": "PCS-503",
                "classroom_id": "L1",
                "time_slot": "14:50 - 15:50",
                "group": "all"
            },
            {
                "teacher_id": "AA04",
                "subject_id": "TCS-502",
                "classroom_id": "R6",
                "time_slot": "16:50 - 17:50",
                "group": "all"
            }
        ]
    },
    "Thursday": {
        "A": [
            {
                "teacher_id": "DT20",
                "subject_id": "XCS-501",
                "classroom_id": "R1",
                "time_slot": "08:00 - 09:00",
                "group": "all"
            },
            {
                "teacher_id": "SP06",
                "subject_id": "TCS-503",
                "classroom_id": "R1",
                "time_slot": "09:00 - 10:00",
                "group": "all"
            },
            {
                "teacher_id": "SS03",
                "subject_id": "TCS-502",
                "classroom_id": "R1",
                "time_slot": "11:00 - 12:00",
                "group": "all"
            },
            {
                "teacher_id": "AB01",
                "subject_id": "TCS-531",
                "classroom_id": "R1",
                "time_slot": "12:00 - 13:00",
                "group": "all"
            }
        ],
        "B": [
            {
                "teacher_id": "DP07",
                "subject_id": "TCS-503",
                "classroom_id": "R2",
                "time_slot": "08:00 - 09:00",
                "group": "all"
            },
            {
                "teacher_id": "AP24",
                "subject_id": "SCS-501",
                "classroom_id": "R2",
                "time_slot": "09:00 - 10:00",
                "group": "all"
            },
            {
                "teacher_id": "PM14",
                "subject_id": "PMA-502",
                "classroom_id": "L1",
                "time_slot": "11:00 - 12:00",
                "group": "all"
            },
            {
                "teacher_id": "AA04",
                "subject_id": "TCS-502",
                "classroom_id": "R2",
                "time_slot": "12:00 - 13:00",
                "group": "all"
            }
        ],
        "C": [
            {
                "teacher_id": "AP24",
                "subject_id": "SCS-501",
                "classroom_id": "R3",
                "time_slot": "08:00 - 09:00",
                "group": "all"
            },
            {
                "teacher_id": "AC05",
                "subject_id": "TCS-503",
                "classroom_id": "R3",
                "time_slot": "09:00 - 10:00",
                "group": "all"
            },
            {
                "teacher_id": "SS03",
                "subject_id": "TCS-502",
                "classroom_id": "R3",
                "time_slot": "11:00 - 12:00",
                "group": "all"
            },
            {
                "teacher_id": "PK02",
                "subject_id": "TCS-531",
                "classroom_id": "R3",
                "time_slot": "12:00 - 13:00",
                "group": "all"
            }
        ],
        "D": [
            {
                "teacher_id": "SP06",
                "subject_id": "TCS-503",
                "classroom_id": "R4",
                "time_slot": "08:00 - 09:00",
                "group": "all"
            },
            {
                "teacher_id": "BJ10",
                "subject_id": "TMA-502",
                "classroom_id": "R4",
                "time_slot": "09:00 - 10:00",
                "group": "all"
            },
            {
                "teacher_id": "RS11",
                "subject_id": "PCS-503",
                "classroom_id": "L1",
                "time_slot": "11:00 - 12:00",
                "group": "all"
            },
            {
                "teacher_id": "RS11",
                "subject_id": "PCS-503",
                "classroom_id": "L1",
                "time_slot": "12:00 - 13:00",
                "group": "all"
            },
            {
                "teacher_id": "AD08",
                "subject_id": "PCS-506",
                "classroom_id": "L1",
                "time_slot": "13:50 - 14:50",
                "group": "all"
            },
            {
                "teacher_id": "AD08",
                "subject_id": "PCS-506",
                "classroom_id": "L1",
                "time_slot": "14:50 - 15:50",
                "group": "all"
            },
            {
                "teacher_id": "AB01",
                "subject_id": "TCS-531",
                "classroom_id": "R4",
                "time_slot": "16:50 - 17:50",
                "group": "all"
            }
        ],
        "E": [
            {
                "teacher_id": "DP07",
                "subject_id": "TCS-503",
                "classroom_id": "R5",
                "time_slot": "08:00 - 09:00",
                "group": "all"
            },
            {
                "teacher_id": "RS11",
                "subject_id": "TMA-502",
                "classroom_id": "R5",
                "time_slot": "09:00 - 10:00",
                "group": "all"
            },
            {
                "teacher_id": "AD08",
                "subject_id": "PMA-502",
                "classroom_id": "L1",
                "time_slot": "11:00 - 12:00",
                "group": "all"
            },
            {
                "teacher_id": "AD08",
                "subject_id": "PMA-502",
                "classroom_id": "L1",
                "time_slot": "12:00 - 13:00",
                "group": "all"
            },
            {
                "teacher_id": "AA15",
                "subject_id": "PMA-502",
                "classroom_id": "L1",
                "time_slot": "13:50 - 14:50",
                "group": "all"
            },
            {
                "teacher_id": "AA15",
                "subject_id": "PMA-502",
                "classroom_id": "L1",
                "time_slot": "14:50 - 15:50",
                "group": "all"
            },
            {
                "teacher_id": "PK02",
                "subject_id": "TCS-531",
                "classroom_id": "R5",
                "time_slot": "16:50 - 17:50",
                "group": "all"
            }
        ],
        "F": [
            {
                "teacher_id": "AC05",
                "subject_id": "TCS-503",
                "classroom_id": "R6",
                "time_slot": "08:00 - 09:00",
                "group": "all"
            },
            {
                "teacher_id": "SJ16",
                "subject_id": "TCS-509",
                "classroom_id": "R6",
                "time_slot": "09:00 - 10:00",
                "group": "all"
            },
            {
                "teacher_id": "AA15",
                "subject_id": "PMA-502",
                "classroom_id": "L2",
                "time_slot": "11:00 - 12:00",
                "group": "all"
            },
            {
                "teacher_id": "AA15",
                "subject_id": "PMA-502",
                "classroom_id": "L2",
                "time_slot": "12:00 - 13:00",
                "group": "all"
            },
            {
                "teacher_id": "DP07",
                "subject_id": "PCS-503",
                "classroom_id": "L2",
                "time_slot": "13:50 - 14:50",
                "group": "all"
            },
            {
                "teacher_id": "DP07",
                "subject_id": "PCS-503",
                "classroom_id": "L2",
                "time_slot": "14:50 - 15:50",
                "group": "all"
            },
            {
                "teacher_id": "JM12",
                "subject_id": "TMA-502",
                "classroom_id": "R6",
                "time_slot": "16:50 - 17:50",
                "group": "all"
            }
        ]
    },
    "Friday": {
        "A": [
            {
                "teacher_id": "RS11",
                "subject_id": "PCS-503",
                "classroom_id": "L2",
                "time_slot": "08:00 - 09:00",
                "group": "all"
            },
            {
                "teacher_id": "SJ16",
                "subject_id": "TCS-509",
                "classroom_id": "R1",
                "time_slot": "09:00 - 10:00",
                "group": "all"
            },
            {
                "teacher_id": "BJ10",
                "subject_id": "TMA-502",
                "classroom_id": "R1",
                "time_slot": "11:00 - 12:00",
                "group": "all"
            },
            {
                "teacher_id": "SS03",
                "subject_id": "TCS-502",
                "classroom_id": "R1",
                "time_slot": "12:00 - 13:00",
                "group": "all"
            }
        ],
        "B": [
            {
                "teacher_id": "AA04",
                "subject_id": "TCS-502",
                "classroom_id": "R2",
                "time_slot": "08:00 - 09:00",
                "group": "all"
            },
            {
                "teacher_id": "AB01",
                "subject_id": "TCS-531",
                "classroom_id": "R2",
                "time_slot": "09:00 - 10:00",
                "group": "all"
            },
            {
                "teacher_id": "JM12",
                "subject_id": "TMA-502",
                "classroom_id": "R2",
                "time_slot": "11:00 - 12:00",
                "group": "all"
            },
            {
                "teacher_id": "AB17",
                "subject_id": "TCS-509",
                "classroom_id": "R2",
                "time_slot": "12:00 - 13:00",
                "group": "all"
            }
        ],
        "C": [
            {
                "teacher_id": "NJ13",
                "subject_id": "TMA-502",
                "classroom_id": "R3",
                "time_slot": "08:00 - 09:00",
                "group": "all"
            },
            {
                "teacher_id": "AC05",
                "subject_id": "TCS-502",
                "classroom_id": "R3",
                "time_slot": "09:00 - 10:00",
                "group": "all"
            },
            {
                "teacher_id": "PM14",
                "subject_id": "PMA-502",
                "classroom_id": "L1",
                "time_slot": "11:00 - 12:00",
                "group": "all"
            },
            {
                "teacher_id": "PK02",
                "subject_id": "TCS-531",
                "classroom_id": "R3",
                "time_slot": "12:00 - 13:00",
                "group": "all"
            }
        ],
        "D": [
            {
                "teacher_id": "HP18",
                "subject_id": "TCS-509",
                "classroom_id": "R4",
                "time_slot": "08:00 - 09:00",
                "group": "all"
            },
            {
                "teacher_id": "AB01",
                "subject_id": "TCS-531",
                "classroom_id": "R4",
                "time_slot": "09:00 - 10:00",
                "group": "all"
            },
            {
                "teacher_id": "RD09",
                "subject_id": "PCS-506",
                "classroom_id": "L1",
                "time_slot": "11:00 - 12:00",
                "group": "all"
            },
            {
                "teacher_id": "RD09",
                "subject_id": "PCS-506",
                "classroom_id": "L1",
                "time_slot": "12:00 - 13:00",
                "group": "all"
            },
            {
                "teacher_id": "DP07",
                "subject_id": "PCS-503",
                "classroom_id": "L1",
                "time_slot": "13:50 - 14:50",
                "group": "all"
            },
            {
                "teacher_id": "DP07",
                "subject_id": "PCS-503",
                "classroom_id": "L1",
                "time_slot": "14:50 - 15:50",
                "group": "all"
            },
            {
                "teacher_id": "SS03",
                "subject_id": "TCS-502",
                "classroom_id": "R4",
                "time_slot": "16:50 - 17:50",
                "group": "all"
            }
        ],
        "E": [
            {
                "teacher_id": "PK02",
                "subject_id": "TCS-531",
                "classroom_id": "R5",
                "time_slot": "08:00 - 09:00",
                "group": "all"
            },
            {
                "teacher_id": "AA04",
                "subject_id": "TCS-502",
                "classroom_id": "R5",
                "time_slot": "09:00 - 10:00",
                "group": "all"
            },
            {
                "teacher_id": "VD25",
                "subject_id": "PCS-503",
                "classroom_id": "L1",
                "time_slot": "11:00 - 12:00",
                "group": "all"
            },
            {
                "teacher_id": "VD25",
                "subject_id": "PCS-503",
                "classroom_id": "L1",
                "time_slot": "12:00 - 13:00",
                "group": "all"
            },
            {
                "teacher_id": "RD09",
                "subject_id": "PCS-506",
                "classroom_id": "L1",
                "time_slot": "13:50 - 14:50",
                "group": "all"
            },
            {
                "teacher_id": "RD09",
                "subject_id": "PCS-506",
                "classroom_id": "L1",
                "time_slot": "14:50 - 15:50",
                "group": "all"
            },
            {
                "teacher_id": "SG19",
                "subject_id": "TCS-509",
                "classroom_id": "R5",
                "time_slot": "16:50 - 17:50",
                "group": "all"
            }
        ],
        "F": [
            {
                "teacher_id": "SJ16",
                "subject_id": "TCS-509",
                "classroom_id": "R6",
                "time_slot": "08:00 - 09:00",
                "group": "all"
            },
            {
                "teacher_id": "AB01",
                "subject_id": "TCS-531",
                "classroom_id": "R6",
                "time_slot": "09:00 - 10:00",
                "group": "all"
            },
            {
                "teacher_id": "SP06",
                "subject_id": "PCS-503",
                "classroom_id": "L2",
                "time_slot": "11:00 - 12:00",
                "group": "all"
            },
            {
                "teacher_id": "SP06",
                "subject_id": "PCS-503",
                "classroom_id": "L2",
                "time_slot": "12:00 - 13:00",
                "group": "all"
            },
            {
                "teacher_id": "AD08",
                "subject_id": "PCS-506",
                "classroom_id": "L1",
                "time_slot": "13:50 - 14:50",
                "group": "all"
            },
            {
                "teacher_id": "AD08",
                "subject_id": "PCS-506",
                "classroom_id": "L1",
                "time_slot": "14:50 - 15:50",
                "group": "all"
            },
            {
                "teacher_id": "DT20",
                "subject_id": "XCS-501",
                "classroom_id": "R6",
                "time_slot": "16:50 - 17:50",
                "group": "all"
            }
        ]
    },
    "Saturday": {
        "A": [
            {
                "teacher_id": "None",
                "subject_id": "Library",
                "classroom_id": "R1",
                "time_slot": "08:00 - 09:00",
                "group": "all"
            },
            {
                "teacher_id": "None",
                "subject_id": "Library",
                "classroom_id": "R1",
                "time_slot": "09:00 - 10:00",
                "group": "all"
            },
            {
                "teacher_id": "None",
                "subject_id": "Library",
                "classroom_id": "R1",
                "time_slot": "11:00 - 12:00",
                "group": "all"
            },
            {
                "teacher_id": "None",
                "subject_id": "Library",
                "classroom_id": "R1",
                "time_slot": "12:00 - 13:00",
                "group": "all"
            }
        ],
        "B": [
            {
                "teacher_id": "None",
                "subject_id": "Library",
                "classroom_id": "R2",
                "time_slot": "08:00 - 09:00",
                "group": "all"
            },
            {
                "teacher_id": "None",
                "subject_id": "Library",
                "classroom_id": "R2",
                "time_slot": "09:00 - 10:00",
                "group": "all"
            },
            {
                "teacher_id": "None",
                "subject_id": "Library",
                "classroom_id": "R2",
                "time_slot": "11:00 - 12:00",
                "group": "all"
            },
            {
                "teacher_id": "None",
                "subject_id": "Library",
                "classroom_id": "R2",
                "time_slot": "12:00 - 13:00",
                "group": "all"
            }
        ],
        "C": [
            {
                "teacher_id": "None",
                "subject_id": "Library",
                "classroom_id": "R3",
                "time_slot": "08:00 - 09:00",
                "group": "all"
            },
            {
                "teacher_id": "None",
                "subject_id": "Library",
                "classroom_id": "R3",
                "time_slot": "09:00 - 10:00",
                "group": "all"
            },
            {
                "teacher_id": "None",
                "subject_id": "Library",
                "classroom_id": "R3",
                "time_slot": "11:00 - 12:00",
                "group": "all"
            },
            {
                "teacher_id": "None",
                "subject_id": "Library",
                "classroom_id": "R3",
                "time_slot": "12:00 - 13:00",
                "group": "all"
            }
        ],
        "D": [
            {
                "teacher_id": "None",
                "subject_id": "Library",
                "classroom_id": "R4",
                "time_slot": "08:00 - 09:00",
                "group": "all"
            },
            {
                "teacher_id": "None",
                "subject_id": "Library",
                "classroom_id": "R4",
                "time_slot": "09:00 - 10:00",
                "group": "all"
            },
            {
                "teacher_id": "RS11",
                "subject_id": "PCS-503",
                "classroom_id": "L2",
                "time_slot": "11:00 - 12:00",
                "group": "all"
            },
            {
                "teacher_id": "RS11",
                "subject_id": "PCS-503",
                "classroom_id": "L2",
                "time_slot": "12:00 - 13:00",
                "group": "all"
            },
            {
                "teacher_id": "AD08",
                "subject_id": "PCS-506",
                "classroom_id": "L1",
                "time_slot": "13:50 - 14:50",
                "group": "all"
            },
            {
                "teacher_id": "AD08",
                "subject_id": "PCS-506",
                "classroom_id": "L1",
                "time_slot": "14:50 - 15:50",
                "group": "all"
            },
            {
                "teacher_id": "None",
                "subject_id": "Library",
                "classroom_id": "R4",
                "time_slot": "16:50 - 17:50",
                "group": "all"
            }
        ],
        "E": [
            {
                "teacher_id": "None",
                "subject_id": "Library",
                "classroom_id": "R5",
                "time_slot": "08:00 - 09:00",
                "group": "all"
            },
            {
                "teacher_id": "None",
                "subject_id": "Library",
                "classroom_id": "R5",
                "time_slot": "09:00 - 10:00",
                "group": "all"
            },
            {
                "teacher_id": "AD08",
                "subject_id": "PMA-502",
                "classroom_id": "L1",
                "time_slot": "11:00 - 12:00",
                "group": "all"
            },
            {
                "teacher_id": "AD08",
                "subject_id": "PMA-502",
                "classroom_id": "L1",
                "time_slot": "12:00 - 13:00",
                "group": "all"
            },
            {
                "teacher_id": "AD08",
                "subject_id": "PCS-506",
                "classroom_id": "L2",
                "time_slot": "13:50 - 14:50",
                "group": "all"
            },
            {
                "teacher_id": "AD08",
                "subject_id": "PCS-506",
                "classroom_id": "L2",
                "time_slot": "14:50 - 15:50",
                "group": "all"
            },
            {
                "teacher_id": "None",
                "subject_id": "Library",
                "classroom_id": "R5",
                "time_slot": "16:50 - 17:50",
                "group": "all"
            }
        ],
        "F": [
            {
                "teacher_id": "None",
                "subject_id": "Library",
                "classroom_id": "R6",
                "time_slot": "08:00 - 09:00",
                "group": "all"
            },
            {
                "teacher_id": "None",
                "subject_id": "Library",
                "classroom_id": "R6",
                "time_slot": "09:00 - 10:00",
                "group": "all"
            },
            {
                "teacher_id": "PM14",
                "subject_id": "PMA-502",
                "classroom_id": "L2",
                "time_slot": "11:00 - 12:00",
                "group": "all"
            },
            {
                "teacher_id": "PM14",
                "subject_id": "PMA-502",
                "classroom_id": "L2",
                "time_slot": "12:00 - 13:00",
                "group": "all"
            },
            {
                "teacher_id": "AD08",
                "subject_id": "PMA-502",
                "classroom_id": "L2",
                "time_slot": "13:50 - 14:50",
                "group": "all"
            },
            {
                "teacher_id": "AD08",
                "subject_id": "PMA-502",
                "classroom_id": "L2",
                "time_slot": "14:50 - 15:50",
                "group": "all"
            },
            {
                "teacher_id": "None",
                "subject_id": "Library",
                "classroom_id": "R6",
                "time_slot": "16:50 - 17:50",
                "group": "all"
            }
        ]
    }
}

days_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
time_order = [
    "08:00 - 09:00",
    "09:00 - 10:00",
    "11:00 - 12:00",
    "12:00 - 13:00",
    "13:50 - 14:50",
    "14:50 - 15:50",
    "16:50 - 17:50"
]


def get_section_table(timetable, section):
    rows = []
    for day, day_data in timetable.items():
        if section in day_data:
            for slot in day_data[section]:
                rows.append({
                    "Day": day,
                    "Time": slot["time_slot"],
                    "Subject": slot["subject_id"],
                })
    df = pd.DataFrame(rows)
    df["Day"] = pd.Categorical(df["Day"], categories=days_order, ordered=True)
    df["Time"] = pd.Categorical(df["Time"], categories=time_order, ordered=True)
    pivoted = df.pivot(index="Day", columns="Time", values="Subject").fillna("")
    return pivoted

# List of sections to generate tables for.
sections = ["A", "B", "C", "D", "E", "F"]

# Create a single HTML string with all section timetables.
html_content = "<html><head><meta charset='utf-8'><title>All Sections Timetable</title></head><body>"
for section in sections:
    table = get_section_table(timetable, section)
    html_content += f"<h2>Section {section}</h2>"
    html_content += table.to_html()
html_content += "</body></html>"

# Write the combined HTML to a file.
with open("all_sections_timetable.html", "w", encoding="utf-8") as f:
    f.write(html_content)
