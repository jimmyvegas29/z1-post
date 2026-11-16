# Modified for Z1 Post by jimmyvegas29, 2026-11-16 (GPL v2; see CHANGELOG.md). Original: Makera Community Fusion plugin by Moinois.
from ...config import ADDIN_NAME, COMPANY_NAME

#
# The configuration file for the Z1 Post add-in (based on the Makera Community Post Processor add-in).
# It contains global variables that can be accessed throughout the add-in.
#

SETTINGS_VERSION = 9

#palettes
POST_PROCESSOR_PALETTE_ID = f'{COMPANY_NAME}_{ADDIN_NAME}_post_processor_palette_id'

CMD_ID = f'{COMPANY_NAME}_{ADDIN_NAME}_postProcessorDialog'
CMD_NAME = 'Z1 Post'
CMD_DESCRIPTION = 'Post-process setups for the Makera Z1 and send the files to the machine over Wi-Fi.'
