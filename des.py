# -*- coding: utf-8 -*-
"""
DES 加密模块
1:1 复刻南京师范大学选课系统前端 des.min.js 的 strEnc 算法（三重 DES + Base64）。

前端逻辑：
    getDesKeys() 返回 ["this", "password", "is"]
    登录密码 = base64.encode( strEnc(明文密码, "this", "password", "is") )
"""

import base64

# ---------------------------------------------------------------
# 标准 DES 的 8 个 S 盒（与前端 des.min.js 完全一致）
# ---------------------------------------------------------------
S_BOXES = [
    [[14, 4, 13, 1, 2, 15, 11, 8, 3, 10, 6, 12, 5, 9, 0, 7],
     [0, 15, 7, 4, 14, 2, 13, 1, 10, 6, 12, 11, 9, 5, 3, 8],
     [4, 1, 14, 8, 13, 6, 2, 11, 15, 12, 9, 7, 3, 10, 5, 0],
     [15, 12, 8, 2, 4, 9, 1, 7, 5, 11, 3, 14, 10, 0, 6, 13]],
    [[15, 1, 8, 14, 6, 11, 3, 4, 9, 7, 2, 13, 12, 0, 5, 10],
     [3, 13, 4, 7, 15, 2, 8, 14, 12, 0, 1, 10, 6, 9, 11, 5],
     [0, 14, 7, 11, 10, 4, 13, 1, 5, 8, 12, 6, 9, 3, 2, 15],
     [13, 8, 10, 1, 3, 15, 4, 2, 11, 6, 7, 12, 0, 5, 14, 9]],
    [[10, 0, 9, 14, 6, 3, 15, 5, 1, 13, 12, 7, 11, 4, 2, 8],
     [13, 7, 0, 9, 3, 4, 6, 10, 2, 8, 5, 14, 12, 11, 15, 1],
     [13, 6, 4, 9, 8, 15, 3, 0, 11, 1, 2, 12, 5, 10, 14, 7],
     [1, 10, 13, 0, 6, 9, 8, 7, 4, 15, 14, 3, 11, 5, 2, 12]],
    [[7, 13, 14, 3, 0, 6, 9, 10, 1, 2, 8, 5, 11, 12, 4, 15],
     [13, 8, 11, 5, 6, 15, 0, 3, 4, 7, 2, 12, 1, 10, 14, 9],
     [10, 6, 9, 0, 12, 11, 7, 13, 15, 1, 3, 14, 5, 2, 8, 4],
     [3, 15, 0, 6, 10, 1, 13, 8, 9, 4, 5, 11, 12, 7, 2, 14]],
    [[2, 12, 4, 1, 7, 10, 11, 6, 8, 5, 3, 15, 13, 0, 14, 9],
     [14, 11, 2, 12, 4, 7, 13, 1, 5, 0, 15, 10, 3, 9, 8, 6],
     [4, 2, 1, 11, 10, 13, 7, 8, 15, 9, 12, 5, 6, 3, 0, 14],
     [11, 8, 12, 7, 1, 14, 2, 13, 6, 15, 0, 9, 10, 4, 5, 3]],
    [[12, 1, 10, 15, 9, 2, 6, 8, 0, 13, 3, 4, 14, 7, 5, 11],
     [10, 15, 4, 2, 7, 12, 9, 5, 6, 1, 13, 14, 0, 11, 3, 8],
     [9, 14, 15, 5, 2, 8, 12, 3, 7, 0, 4, 10, 1, 13, 11, 6],
     [4, 3, 2, 12, 9, 5, 15, 10, 11, 14, 1, 7, 6, 0, 8, 13]],
    [[4, 11, 2, 14, 15, 0, 8, 13, 3, 12, 9, 7, 5, 10, 6, 1],
     [13, 0, 11, 7, 4, 9, 1, 10, 14, 3, 5, 12, 2, 15, 8, 6],
     [1, 4, 11, 13, 12, 3, 7, 14, 10, 15, 6, 8, 0, 5, 9, 2],
     [6, 11, 13, 8, 1, 4, 10, 7, 9, 5, 0, 15, 14, 2, 3, 12]],
    [[13, 2, 8, 4, 6, 15, 11, 1, 10, 9, 3, 14, 5, 0, 12, 7],
     [1, 15, 13, 8, 10, 3, 7, 4, 12, 5, 6, 11, 0, 14, 9, 2],
     [7, 11, 4, 1, 9, 12, 14, 2, 0, 6, 10, 13, 15, 3, 5, 8],
     [2, 1, 14, 7, 4, 10, 8, 13, 15, 12, 9, 0, 3, 5, 6, 11]],
]

# 16 轮循环左移位数
_SHIFT = [1, 1, 2, 2, 2, 2, 2, 2, 1, 2, 2, 2, 2, 2, 2, 1]

_HEX4 = {0: "0", 1: "1", 2: "2", 3: "3", 4: "4", 5: "5", 6: "6", 7: "7",
         8: "8", 9: "9", 10: "A", 11: "B", 12: "C", 13: "D", 14: "E", 15: "F"}


def _xor(a, b):
    return [a[i] ^ b[i] for i in range(len(a))]


def _str_to_bt(s):
    """字符串 -> 64 位比特数组（每字符占 16 位，高位在前）。不足 4 字符补 0。"""
    a = [0] * 64
    n = min(len(s), 4)
    for i in range(n):
        c = ord(s[i])
        for t in range(16):
            a[16 * i + t] = (c >> (15 - t)) & 1
    return a


def _get_key_bytes(key):
    """密钥字符串按 4 字符一组，每组转成 64 位比特数组。"""
    e = []
    length = len(key)
    n = length // 4
    for s in range(n):
        e.append(_str_to_bt(key[4 * s: 4 * s + 4]))
    if length % 4 > 0:
        e.append(_str_to_bt(key[4 * n:]))
    return e


def _bt4_to_hex(bits4):
    val = (bits4[0] << 3) | (bits4[1] << 2) | (bits4[2] << 1) | bits4[3]
    return _HEX4[val]


def _bt64_to_hex(bits):
    out = ""
    for i in range(16):
        out += _bt4_to_hex(bits[4 * i: 4 * i + 4])
    return out


def _generate_keys(key64):
    """DES 密钥调度：PC-1 -> 16 轮循环左移 -> PC-2，返回 16 个 48 位子密钥。"""
    e = [0] * 56
    a = [[0] * 48 for _ in range(16)]
    # PC-1
    for t in range(7):
        for j in range(8):
            k = 7 - j
            e[8 * t + j] = key64[8 * k + t]
    for t in range(16):
        # 循环左移
        for _ in range(_SHIFT[t]):
            s0 = e[0]
            s28 = e[28]
            for k in range(27):
                e[k] = e[k + 1]
                e[28 + k] = e[29 + k]
            e[27] = s0
            e[55] = s28
        # PC-2
        c = [0] * 48
        c[0] = e[13]; c[1] = e[16]; c[2] = e[10]; c[3] = e[23]; c[4] = e[0]; c[5] = e[4]; c[6] = e[2]; c[7] = e[27]
        c[8] = e[14]; c[9] = e[5]; c[10] = e[20]; c[11] = e[9]; c[12] = e[22]; c[13] = e[18]; c[14] = e[11]; c[15] = e[3]
        c[16] = e[25]; c[17] = e[7]; c[18] = e[15]; c[19] = e[6]; c[20] = e[26]; c[21] = e[19]; c[22] = e[12]; c[23] = e[1]
        c[24] = e[40]; c[25] = e[51]; c[26] = e[30]; c[27] = e[36]; c[28] = e[46]; c[29] = e[54]; c[30] = e[29]; c[31] = e[39]
        c[32] = e[50]; c[33] = e[44]; c[34] = e[32]; c[35] = e[47]; c[36] = e[43]; c[37] = e[48]; c[38] = e[38]; c[39] = e[55]
        c[40] = e[33]; c[41] = e[52]; c[42] = e[45]; c[43] = e[41]; c[44] = e[49]; c[45] = e[35]; c[46] = e[28]; c[47] = e[31]
        a[t] = c
    return a


def _init_permute(r):
    e = [0] * 64
    m = 1
    n = 0
    for i in range(4):
        k = 0
        for j in range(7, -1, -1):
            e[8 * i + k] = r[8 * j + m]
            e[8 * i + k + 32] = r[8 * j + n]
            k += 1
        m += 2
        n += 2
    return e


def _finally_permute(r):
    e = [0] * 64
    e[0] = r[39]; e[1] = r[7]; e[2] = r[47]; e[3] = r[15]; e[4] = r[55]; e[5] = r[23]; e[6] = r[63]; e[7] = r[31]
    e[8] = r[38]; e[9] = r[6]; e[10] = r[46]; e[11] = r[14]; e[12] = r[54]; e[13] = r[22]; e[14] = r[62]; e[15] = r[30]
    e[16] = r[37]; e[17] = r[5]; e[18] = r[45]; e[19] = r[13]; e[20] = r[53]; e[21] = r[21]; e[22] = r[61]; e[23] = r[29]
    e[24] = r[36]; e[25] = r[4]; e[26] = r[44]; e[27] = r[12]; e[28] = r[52]; e[29] = r[20]; e[30] = r[60]; e[31] = r[28]
    e[32] = r[35]; e[33] = r[3]; e[34] = r[43]; e[35] = r[11]; e[36] = r[51]; e[37] = r[19]; e[38] = r[59]; e[39] = r[27]
    e[40] = r[34]; e[41] = r[2]; e[42] = r[42]; e[43] = r[10]; e[44] = r[50]; e[45] = r[18]; e[46] = r[58]; e[47] = r[26]
    e[48] = r[33]; e[49] = r[1]; e[50] = r[41]; e[51] = r[9]; e[52] = r[49]; e[53] = r[17]; e[54] = r[57]; e[55] = r[25]
    e[56] = r[32]; e[57] = r[0]; e[58] = r[40]; e[59] = r[8]; e[60] = r[48]; e[61] = r[16]; e[62] = r[56]; e[63] = r[24]
    return e


def _expand_permute(r):
    e = [0] * 48
    for i in range(8):
        e[6 * i + 0] = r[31] if i == 0 else r[4 * i - 1]
        e[6 * i + 1] = r[4 * i + 0]
        e[6 * i + 2] = r[4 * i + 1]
        e[6 * i + 3] = r[4 * i + 2]
        e[6 * i + 4] = r[4 * i + 3]
        e[6 * i + 5] = r[0] if i == 7 else r[4 * i + 4]
    return e


def _p_permute(r):
    e = [0] * 32
    e[0] = r[15]; e[1] = r[6]; e[2] = r[19]; e[3] = r[20]; e[4] = r[28]; e[5] = r[11]; e[6] = r[27]; e[7] = r[16]
    e[8] = r[0]; e[9] = r[14]; e[10] = r[22]; e[11] = r[25]; e[12] = r[4]; e[13] = r[17]; e[14] = r[30]; e[15] = r[9]
    e[16] = r[1]; e[17] = r[7]; e[18] = r[23]; e[19] = r[13]; e[20] = r[31]; e[21] = r[26]; e[22] = r[2]; e[23] = r[8]
    e[24] = r[18]; e[25] = r[12]; e[26] = r[29]; e[27] = r[5]; e[28] = r[21]; e[29] = r[10]; e[30] = r[3]; e[31] = r[24]
    return e


def _s_box_permute(r):
    e = [0] * 32
    for m in range(8):
        row = (r[6 * m] << 1) | r[6 * m + 5]
        col = (r[6 * m + 1] << 3) | (r[6 * m + 2] << 2) | (r[6 * m + 3] << 1) | r[6 * m + 4]
        val = S_BOXES[m][row][col]
        e[4 * m + 0] = (val >> 3) & 1
        e[4 * m + 1] = (val >> 2) & 1
        e[4 * m + 2] = (val >> 1) & 1
        e[4 * m + 3] = val & 1
    return e


def _enc(block64, key64):
    """标准 DES 加密：64 位明文 + 64 位密钥 -> 64 位密文。"""
    keys = _generate_keys(key64)
    n = _init_permute(block64)
    t = n[:32]
    s = n[32:]
    for c in range(16):
        o = t[:]
        t = s[:]
        b = _xor(_p_permute(_s_box_permute(_xor(_expand_permute(s), keys[c]))), o)
        s = b
    k = s + t
    return _finally_permute(k)


def str_enc(data, key1, key2, key3):
    """
    与前端 strEnc(data, key1, key2, key3) 完全等价：
    数据按 4 字符分组，每组依次用 key1/key2/key3 的每个 64 位子密钥做 DES 加密，结果转 hex。
    """
    keys1 = _get_key_bytes(key1)
    keys2 = _get_key_bytes(key2)
    keys3 = _get_key_bytes(key3)

    out = ""
    length = len(data)
    n = length // 4
    for v in range(n):
        block = _str_to_bt(data[4 * v: 4 * v + 4])
        for k in keys1:
            block = _enc(block, k)
        for k in keys2:
            block = _enc(block, k)
        for k in keys3:
            block = _enc(block, k)
        out += _bt64_to_hex(block)
    if length % 4 > 0:
        block = _str_to_bt(data[4 * n:])
        for k in keys1:
            block = _enc(block, k)
        for k in keys2:
            block = _enc(block, k)
        for k in keys3:
            block = _enc(block, k)
        out += _bt64_to_hex(block)
    return out


def encrypt_password(password):
    """登录密码加密：base64( strEnc(password, 'this', 'password', 'is') )。"""
    hex_str = str_enc(password, "this", "password", "is")
    return base64.b64encode(hex_str.encode("ascii")).decode("ascii")


if __name__ == "__main__":
    import sys
    pwd = sys.argv[1] if len(sys.argv) > 1 else "123456"
    print("明文:", pwd)
    print("加密:", encrypt_password(pwd))
