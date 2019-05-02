from helper.extract_data import df_parser

def test_df_parser():
    test1 = """Filesystem               Size     Used     Free   Blksize
    /dev                     1.8G   116.0K     1.8G   4096
    /sys/fs/cgroup           1.8G    12.0K     1.8G   4096
    /mnt                     1.8G     0.0K     1.8G   4096
    /system                  2.4G     1.6G   770.9M   4096
    /data                   53.6G     3.1G    50.4G   4096
    /cache                 418.4M   976.0K   417.5M   4096
    /protect_f               3.9M    68.0K     3.8M   4096
    /protect_s               6.0M    60.0K     6.0M   4096
    /nvdata                 27.5M     6.8M    20.7M   4096
    /nvcfg                   3.9M    80.0K     3.8M   4096
    /custom                495.9M    26.8M   469.1M   4096
    /storage                 1.8G     0.0K     1.8G   4096
    /mnt/runtime/default/emulated: Permission denied
    /storage/emulated       53.5G     3.2G    50.3G   4096
    /mnt/runtime/read/emulated: Permission denied
    /mnt/runtime/write/emulated: Permission denied"""

    test2 = """Filesystem  512-blocks Free %Used  Iused %Iused Mounted on
    /dev/hd4          131072    107536   18%     1652    12% /
    /dev/hd2         4325376   2165800   50%    27365    11% /usr
    /dev/hd9var       262144    242320    8%      389     2% /var
    /dev/hd3          131072    129192    2%       28     1% /tmp
    /dev/hd1          262144    260944    1%       60     1% /home
    /proc                  -         -    -         -     -  /proc
    /dev/hd10opt      131072     75360   43%      649     8% /opt
    /dev/oraHome    16777216   6999616   59%    64843     8% /oraHome
    /dev/T600      348127232  86530624   76%     4949     1% /oradata"""

    test3 = """Filesystem          1K-blocks      Used  Available Use% Mounted on
    devtmpfs                         8170452         0    8170452   0% /dev
    tmpfs                            8218492    360816    7857676   5% /dev/shm
    tmpfs                            8218492      1728    8216764   1% /run
    tmpfs                            8218492         0    8218492   0% /sys/fs/cgroup
    /dev/mapper/fedora--main-root   30832548  11873020   17370280  41% /
    tmpfs                            8218492     21740    8196752   1% /tmp
    /dev/nvme0n1p1                    487634    200156     257782  44% /boot
    /dev/nvme0n1p2                    204580     18344     186236   9% /boot/efi
    /dev/mapper/fedora--main-home  199182696 149976092   39019036  80% /home
    tmpfs                            1643696       144    1643552   1% /run/user/975
    /dev/sda1                      960186400  47752496  863589360   6% /mnt/storage
    000.000.000.000:/mnt/M1       1682687488     18432 1682669056   1% /home/m"""

    test4 = """Filesystem          Size  Used Avail Use% Mounted on
    devtmpfs                       7.8G     0  7.8G   0% /dev
    tmpfs                          7.9G  321M  7.6G   4% /dev/shm
    tmpfs                          7.9G  1.7M  7.9G   1% /run
    tmpfs                          7.9G     0  7.9G   0% /sys/fs/cgroup
    /dev/mapper/fedora--main-root   30G   12G   17G  41% /
    tmpfs                          7.9G   22M  7.9G   1% /tmp
    /dev/nvme0n1p1                 477M  196M  252M  44% /boot
    /dev/nvme0n1p2                 200M   18M  182M   9% /boot/efi
    /dev/mapper/fedora--main-home  190G  144G   38G  80% /home
    tmpfs                          1.6G  144K  1.6G   1% /run/user/975
    /dev/sda1                       916    55   861   6% /mnt/storage
    000.000.000.000:/mnt/M1        1.6T   18M  1.6T   1% /home/m"""

    for test_case in [test1, test2, test3, test4]:
        assert df_parser(test_case)


