# Copyright 2026 Syed Basim Ali
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Project Sonus: Real-Time Audio Analysis and Volume Management.

Application for monitoring a live audio stream, calculating loudness
metrics according to ITU-R BS.1770 (LUFS), and providing real-time feedback
to help users manage safe listening levels and daily sound exposure dose.

Author: Syed Basim Ali <basim.ali.contact@gmail.com>
License: Apache-2.0
"""

__version__ = "1.0.0.0"
__author__ = "Syed Basim Ali"
__email__ = "basim.ali.contact@gmail.com"
__license__ = "Apache-2.0"

if __name__ == "__main__":
    logo = r"""
    ██████╗ ██████╗  ██████╗      ██╗███████╗ ██████╗████████╗
    ██╔══██╗██╔══██╗██╔═══██╗     ██║██╔════╝██╔════╝╚══██╔══╝
    ██████╔╝██████╔╝██║   ██║     ██║█████╗  ██║        ██║   
    ██╔═══╝ ██╔══██╗██║   ██║██   ██║██╔══╝  ██║        ██║   
    ██║     ██║  ██║╚██████╔╝╚█████╔╝███████╗╚██████╗   ██║   
    ╚═╝     ╚═╝  ╚═╝ ╚═════╝  ╚════╝ ╚══════╝ ╚═════╝   ╚═╝   
                                                            
        ███████╗ ██████╗ ███╗   ██╗██╗   ██╗███████╗          
        ██╔════╝██╔═══██╗████╗  ██║██║   ██║██╔════╝          
        ███████╗██║   ██║██╔██╗ ██║██║   ██║███████╗          
        ╚════██║██║   ██║██║╚██╗██║██║   ██║╚════██║          
        ███████║╚██████╔╝██║ ╚████║╚██████╔╝███████║          
        ╚══════╝ ╚═════╝ ╚═╝  ╚═══╝ ╚═════╝ ╚══════╝          
    """
    print(logo)
    print(f"Project Sonus - Version {__version__} by {__author__}")
    print("This is a package. Run 'python __main__.py' to start the application.")
