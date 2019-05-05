from helper.extract_data import df_parser

def test_df_parser():
    # sizes for (syntactically) easier calculation
    K = lambda x: int(x*1024)
    M = lambda x: int(x*1024**2)
    G = lambda x: int(x*1024**3)
    T = lambda x: int(x*1024**4)

    test1 = """Filesystem    Size     Used     Free   Blksize
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

    test1_results = [
        ("/dev", G(1.8), K(116), G(1.8)),
        ("/sys/fs/cgroup", G(1.8), K(12), G(1.8)),
        ("/mnt", G(1.8), 0, G(1.8)),
        ("/system", G(2.4), G(1.6), M(770.9)),
        ("/data", G(53.6), G(3.1), G(50.4)),
        ("/cache", M(418.4), K(976), M(417.5)),
        ("/protect_f", M(3.9), K(68), M(3.8)),
        ("/protect_s", M(6), K(60), M(6)),
        ("/nvdata", M(27.5), M(6.8), M(20.7)),
        ("/nvcfg", M(3.9), K(80), M(3.8)),
        ("/custom", M(495.9), M(26.8), M(469.1)),
        ("/storage", G(1.8), 0, G(1.8)),
        ("/mnt/runtime/default/emulated:", -1, -1, -1),
        ("/storage/emulated", G(53.5), G(3.2), G(50.3)),
        ("/mnt/runtime/read/emulated:", -1, -1, -1),
        ("/mnt/runtime/write/emulated:", -1, -1, -1),
    ]

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
    test2_results = [(None,None,None,None)]

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
    test3_results = [(None,None,None,None)]

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
    test4_results = [(None,None,None,None)]

    test_cases = [
        test1,
        #test2,test3,test4
    ]
    test_results = [
        test1_results,
        #test2_results,test3_results,test4_results
    ]

    for test_case, expected_results in zip(test_cases, test_results):
        actual_results = df_parser(test_case)
        for line_actual, line_expected in zip(actual_results, expected_results):
            #print(line_actual, line_expected)
            assert line_actual == line_expected
