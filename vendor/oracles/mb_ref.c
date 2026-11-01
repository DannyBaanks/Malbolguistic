/* Fast reference Malbolge interpreter (standard semantics, Ben Olmstead specification).
 * Usage: mb_ref prog.mal [max_steps] < input > output
 */
#include <stdio.h>
#include <stdlib.h>
#include <ctype.h>
#include <string.h>
#include <errno.h>

static const char xlat1[] = "+b(29e*j1VMEKLyC})8&m#~W>qxdRp0wkrUo[D7,XTcA\"lI.v%{gJh4G\\-=O@5`_3i<?Z';FNQuY]szf$!BS/|t:Pn6^Ha";
static const char xlat2[] = "5z]&gqtyfr$(we4{WP)H-Zn,[%\\3dL+Q;>U!pJS72FhOA1CB6v^=I_0/8|jsb9m<.TVac`uY*MK'X~xDl}REokN:#?G\"i@";

static inline unsigned short op(unsigned short x, unsigned short y) {
    unsigned short i = 0;
    static const unsigned short p9[5] = { 1, 9, 81, 729, 6561 };
    static const unsigned short o[9][9] = {
        { 4, 3, 3, 1, 0, 0, 1, 0, 0 },
        { 4, 3, 5, 1, 0, 2, 1, 0, 2 },
        { 5, 5, 4, 2, 2, 1, 2, 2, 1 },
        { 4, 3, 3, 1, 0, 0, 7, 6, 6 },
        { 4, 3, 5, 1, 0, 2, 7, 6, 8 },
        { 5, 5, 4, 2, 2, 1, 8, 8, 7 },
        { 7, 6, 6, 7, 6, 6, 4, 3, 3 },
        { 7, 6, 8, 7, 6, 8, 4, 3, 5 },
        { 8, 8, 7, 8, 8, 7, 5, 5, 4 },
    };
    for (int j = 0; j < 5; j++)
        i += o[y / p9[j] % 9][x / p9[j] % 9] * p9[j];
    return i;
}

int main(int argc, char **argv) {
    if (argc < 2 || argc > 3) {
        fprintf(stderr, "Usage: %s <program.mal> [max_steps]\n", argv[0]);
        return 1;
    }
    unsigned long long max_steps = 100000000ULL;
    if (argc == 3) {
        char *end;
        if (!argv[2][0] || strspn(argv[2], "0123456789") != strlen(argv[2])) {
            fprintf(stderr, "INVALID_BUDGET: expected unsigned decimal integer\n");
            return 1;
        }
        errno = 0;
        max_steps = strtoull(argv[2], &end, 10);
        if (errno || *end) {
            fprintf(stderr, "INVALID_BUDGET: out of range\n");
            return 1;
        }
    }
    FILE *f = fopen(argv[1], "rb");
    if (!f) {
        fprintf(stderr, "Cannot open %s\n", argv[1]);
        return 1;
    }
    static unsigned short mem[59049];
    unsigned int i = 0;
    int x;
    while ((x = fgetc(f)) != EOF) {
        if (isspace(x)) continue;
        if (x < 33 || x > 126) {
            fprintf(stderr, "Invalid character 0x%02x\n", x);
            fclose(f);
            return 1;
        }
        if (i == 59049) {
            fprintf(stderr, "Input program too long\n");
            fclose(f);
            return 1;
        }
        if (!strchr("ji*p</vo", xlat1[(x - 33 + i) % 94])) {
            fprintf(stderr, "INVALID_OPCODE: cell %u\n", i);
            fclose(f);
            return 1;
        }
        mem[i++] = (unsigned short)x;
    }
    if (ferror(f)) {
        fprintf(stderr, "READ_ERROR\n");
        fclose(f);
        return 1;
    }
    fclose(f);
    if (i < 2) {
        fprintf(stderr, "TOO_SHORT: need at least two cells\n");
        return 1;
    }
    while (i < 59049) {
        mem[i] = op(mem[i - 1], mem[i - 2]);
        i++;
    }

    unsigned short a = 0, c = 0, d = 0;
    unsigned long long step = 0;
    while (step < max_steps) {
        if (mem[c] < 33 || mem[c] > 126) {
            /* Olmstead stalls here. Report it instead of inventing a NOP. */
            fprintf(stderr, "NONPRINTABLE_PC: cell %u value %u step %llu\n", c, mem[c], step);
            return 3;
        }
        char instr = xlat1[(mem[c] - 33 + c) % 94];
        if (instr == 'j') d = mem[d];
        else if (instr == 'i') c = mem[d];
        else if (instr == '*') a = mem[d] = mem[d] / 3 + (mem[d] % 3) * 19683;
        else if (instr == 'p') a = mem[d] = op(a, mem[d]);
        else if (instr == '<') putchar((int)(a & 255));
        else if (instr == '/') {
            int in_ch = getchar();
            if (ferror(stdin)) { fprintf(stderr, "INPUT_ERROR\n"); return 4; }
            a = (in_ch == EOF) ? 59048 : (unsigned short)in_ch;
        }
        else if (instr == 'v') {
            if (fflush(stdout) || ferror(stdout)) { fprintf(stderr, "OUTPUT_ERROR\n"); return 4; }
            return 0;
        }

        /* Jump encrypts its destination; self-modification can also leave
         * a nonprintable value here. Never index xlat2 out of bounds. */
        if (mem[c] < 33 || mem[c] > 126) {
            fprintf(stderr, "INVALID_ENCRYPTION: cell %u value %u step %llu\n", c, mem[c], step);
            return 3;
        }
        mem[c] = (unsigned short)xlat2[mem[c] - 33];
        c = (c == 59048) ? 0 : c + 1;
        d = (d == 59048) ? 0 : d + 1;
        step++;
    }
    fprintf(stderr, "MAX_STEPS: %llu (HALT not reached)\n", max_steps);
    return 2;
}
