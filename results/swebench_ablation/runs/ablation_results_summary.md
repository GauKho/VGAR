# Bảng tổng hợp kết quả Ablation Matrix

5 task thuộc 4 repo; 30 ô task × arm. Hiện có 30 report grading: 16 PASS và 14 FAIL theo official SWE-bench; đủ grading cho 30/30 ô. Không dùng các số này như điểm trên toàn bộ SWE-bench Verified.

| Task             | Repo                  | Arm | F2P  | P2P       | Resolved (SWE-bench) | Input tokens | Output tokens |
| ---------------- | --------------------- | --- | ---- | --------- | -------------------- | ------------ | ------------- |
| Sphinx-10673     | sphinx-doc/sphinx     | A0  | 1/1  | 9/9       | PASS                 | 555067       | 16378         |
| Sphinx-10673     | sphinx-doc/sphinx     | A1  | 1/1  | 9/9       | PASS                 | 211718       | 11356         |
| Sphinx-10673     | sphinx-doc/sphinx     | A2  | 1/1  | 9/9       | PASS                 | 211312       | 15743         |
| Sphinx-10673     | sphinx-doc/sphinx     | A3  | 1/1  | 9/9       | PASS                 | 256693       | 14023         |
| Sphinx-10673     | sphinx-doc/sphinx     | A4  | 1/1  | 9/9       | PASS                 | 269516       | 13252         |
| Sphinx-10673     | sphinx-doc/sphinx     | A5  | 1/1  | 9/9       | PASS                 | 531493       | 42221         |
| Xarray-6992      | pydata/xarray         | A0  | 0/12 | 945/945   | FAIL                 | 216264       | 7408          |
| Xarray-6992      | pydata/xarray         | A1  | 0/12 | 945/945   | FAIL                 | 341184       | 7336          |
| Xarray-6992      | pydata/xarray         | A2  | 1/12 | 945/945   | FAIL                 | 94128        | 7507          |
| Xarray-6992      | pydata/xarray         | A3  | 0/12 | 945/945   | FAIL                 | 88312        | 6582          |
| Xarray-6992      | pydata/xarray         | A4  | 0/12 | 945/945   | FAIL                 | 302940       | 6817          |
| Xarray-6992      | pydata/xarray         | A5  | 0/12 | 945/945   | FAIL                 | 170817       | 5958          |
| Xarray-3993      | pydata/xarray         | A0  | 0/2  | 2398/2398 | FAIL                 | 95434        | 4926          |
| Xarray-3993      | pydata/xarray         | A1  | 2/2  | 2398/2398 | PASS                 | 822779       | 45660         |
| Xarray-3993      | pydata/xarray         | A2  | 0/2  | 2398/2398 | FAIL                 | 119841       | 10507         |
| Xarray-3993      | pydata/xarray         | A3  | 2/2  | 2398/2398 | PASS                 | 122329       | 11814         |
| Xarray-3993      | pydata/xarray         | A4  | 2/2  | 2398/2398 | PASS                 | 119475       | 10857         |
| Xarray-3993      | pydata/xarray         | A5  | 2/2  | 2398/2398 | PASS                 | 225587       | 17768         |
| Pylint-4604      | pylint-dev/pylint     | A0  | 0/21 | 0/0       | FAIL                 | 126287       | 7635          |
| Pylint-4604      | pylint-dev/pylint     | A1  | 0/21 | 0/0       | FAIL                 | 113065       | 4617          |
| Pylint-4604      | pylint-dev/pylint     | A2  | 0/21 | 0/0       | FAIL                 | 186728       | 8760          |
| Pylint-4604      | pylint-dev/pylint     | A3  | 0/21 | 0/0       | FAIL                 | 51738        | 6702          |
| Pylint-4604      | pylint-dev/pylint     | A4  | 0/21 | 0/0       | FAIL                 | 384165       | 10912         |
| Pylint-4604      | pylint-dev/pylint     | A5  | 0/21 | 0/0       | FAIL                 | 182822       | 10117         |
| Matplotlib-14623 | matplotlib/matplotlib | A0  | 1/1  | 400/400   | PASS                 | 126622       | 6811          |
| Matplotlib-14623 | matplotlib/matplotlib | A1  | 1/1  | 400/400   | PASS                 | 382288       | 10404         |
| Matplotlib-14623 | matplotlib/matplotlib | A2  | 1/1  | 400/400   | PASS                 | 84756        | 7060          |
| Matplotlib-14623 | matplotlib/matplotlib | A3  | 1/1  | 400/400   | PASS                 | 196493       | 10065         |
| Matplotlib-14623 | matplotlib/matplotlib | A4  | 1/1  | 400/400   | PASS                 | 126250       | 13835         |
| Matplotlib-14623 | matplotlib/matplotlib | A5  | 1/1  | 400/400   | PASS                 | 544647       | 13077         |

## Bảng 2. Tổng hợp Resolved rate theo arm

Trong bảng này, **task hoàn thành là task đạt `Resolved=PASS`**, không phải chỉ hoàn tất chạy agent hoặc grading. Công thức: **Resolved rate = số task đạt PASS / 5 × 100%**.

| Arm | Tasks resolved / 5 | Resolved rate |
| --- | ------------------ | ------------- |
| A0  | 2/5                | 40%           |
| A1  | 3/5                | 60%           |
| A2  | 2/5                | 40%           |
| A3  | 3/5                | 60%           |
| A4  | 3/5                | 60%           |
| A5  | 3/5                | 60%           |
