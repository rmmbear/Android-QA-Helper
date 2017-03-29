import sys
from helper.cli import main

try:
    main()
except KeyboardInterrupt:
    sys.exit("")

