from enum import Enum

class ComplaintType(Enum):
    GLASS_DAMAGE = "Glass Damage"
    PM = "PM"
    # Add other complaint types as needed

class GlassDamageType(Enum):
    WINDSHIELD_CRACK = "Windshield Crack"
    WINDSHIELD_CHIP = "Windshield Chip"
    SIDE_REAR_WINDOW_DAMAGE = "Side/Rear Window Damage"
    UNKNOWN = "I don't know"

# Example usage:
# ComplaintType.GLASS_DAMAGE.value
# GlassDamageType.WINDSHIELD_CRACK.value
