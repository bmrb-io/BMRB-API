#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include <string.h>
#include <unistd.h>
#include <limits.h>

// We will use these to access the elements within the struct array
#define fullpdbname_pos 0
#define pdb_pos 1
#define model_pos 0
#define hydrogen_positions_pos 2
#define molprobity_flips_pos 3
#define backbone_trim_state_pos 4
#define assembly_id_pos 5
#define clashscore_pos 1
#define clashscore_less40_pos 2
#define cbeta_outlier_pos 3
#define numcbeta_pos 4
#define rota_less1pct_pos 5
#define numrota_pos 6
#define ramaoutlier_pos 7
#define ramaallowed_pos 8
#define ramafavored_pos 9
#define numrama_pos 10
#define numbadbonds_pos 11
#define numbonds_pos 12
#define pct_badbonds_pos 13
#define pct_resbadbonds_pos 14
#define numbadangles_pos 15
#define numangles_pos 16
#define pct_badangles_pos 17
#define pct_resbadangles_pos 18
#define molprobityscore_pos 19
#define numpperp_outlier_pos 20
#define numpperp_pos 21
#define numsuite_outlier_pos 22
#define numsuite_pos 23
#define entry_id_pos 6
#define structure_val_oneline_list_id_pos 7
#define macromolecule_types_pos 8

// The following defines are not tables in the csv, but added calculated data
#define cbeta_normalized_pos 0
#define rota_normalized_pos 1
#define rama_normalized_pos 2
#define pperp_normalized_pos 3
#define suite_normalized_pos 4

// Use a struct to keep track of each row
struct record {
    char text_records[9][16];
    float float_records[24];
    float calculated_records[5];
};

struct search_element {
    double key;
    double value;
    int num_values;
};

float get_normalized(float top, float bottom){
    if (top == -1 || bottom == -1 || bottom == 0){ return -1; }
    return roundf((top/bottom) * 10000)/100;
}

struct record * parse_file(char to_read_from[], unsigned long * num_rows){

    // Needed to read from file
    FILE * fp;
    char * line = NULL;
    size_t len = 0;
    ssize_t read;

    // Open the file
    fp = fopen(to_read_from, "r");
    if (fp == NULL) {
        fprintf(stderr, "Can't open input file: %s\n", to_read_from);
        exit(1);
    }

    // First count the number of lines
    int c;
    unsigned long line_num = 0;
    while ( (c=fgetc(fp)) != EOF ) {
        if ( c == '\n' )
            line_num++;
    }
    // Go back to the beggining of the file
    fseek(fp, 0, SEEK_SET);

    // Allocate the record array
    struct record *result_array = malloc(line_num * sizeof(struct record));

    // Temporary text array to use during reading
    char tmp_text[31][16];

    unsigned long cur_position = 0;
    while ((read = getline(&line, &len, fp)) != -1) {

        // Remove the trailing newline
        if (line[strlen(line)-1] == '\n'){ line[strlen(line)-1] = 0;}

        // Create a pointer to the current record we are reading in
        struct record *a_record = &result_array[cur_position];

        // Read in all the records
        for (int i=0; i<33;i++){ snprintf(tmp_text[i], sizeof(tmp_text[i]), "%s", strsep(&line, ":"));}

        int float_positions[] = {2,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29};
        int text_positions[] = {0,1,3,4,5,6,30,31,32};

        for (int i=0; i< sizeof(text_positions)/sizeof(int); i++){
            snprintf(a_record->text_records[i], sizeof(a_record->text_records[i]), "%s", tmp_text[text_positions[i]]);
        }

        for (int i=0; i< sizeof(float_positions)/sizeof(int); i++){
            if (strlen(tmp_text[float_positions[i]]) == 0){
                a_record->float_records[i] = -1;
            } else {
                a_record->float_records[i] = atof(tmp_text[float_positions[i]]);
            }
        }

        a_record->calculated_records[cbeta_normalized_pos] = get_normalized(a_record->float_records[cbeta_outlier_pos], a_record->float_records[numcbeta_pos]);
        a_record->calculated_records[rota_normalized_pos] = get_normalized(a_record->float_records[rota_less1pct_pos], a_record->float_records[numrota_pos]);
        a_record->calculated_records[rama_normalized_pos] = get_normalized(a_record->float_records[ramaoutlier_pos], a_record->float_records[numrama_pos]);
        a_record->calculated_records[pperp_normalized_pos] = get_normalized(a_record->float_records[numpperp_outlier_pos], a_record->float_records[numpperp_pos]);
        a_record->calculated_records[suite_normalized_pos] = get_normalized(a_record->float_records[numsuite_outlier_pos], a_record->float_records[numsuite_pos]);

        cur_position++;
    }

    *num_rows = cur_position;
    return result_array;
}

int sort_float(const void *a, const void *b){
    float fa = *(const float*) a;
    float fb = *(const float*) b;
    return (fa > fb) - (fa < fb);
}

struct search_element * generate_search_field(float * array, unsigned long * size){

    unsigned long size_copy = (unsigned long)*size;

    int num_unique = 1;
    float cur_val = array[0];
    for (int x=1; x<size_copy; x++){
        if (cur_val != array[x]){
            num_unique++;
            cur_val = array[x];
        }
    }

    struct search_element * ray  = malloc(num_unique * sizeof(struct search_element));

    // Set the first value
    struct search_element * a_rec;

    num_unique = 0;
    cur_val = array[0];
    unsigned long previous_find = 0;

    for (int x=1; x<size_copy; x++){
        if (cur_val != array[x]){
            a_rec = &ray[num_unique];
            a_rec->key = cur_val;
            a_rec->value = ((float)(previous_find)/(float)size_copy) * 100;
            a_rec->num_values = x - previous_find;

            previous_find = x;
            num_unique++;
            cur_val = array[x];
        }
    }

    *size = num_unique;

    return ray;
}

float calculate_percentile(struct search_element * array, unsigned long n, float search){

    unsigned long first, last, middle;

    first = 0;
    last = n - 1;
    middle = ( first + last ) / 2;

    struct search_element * a;

    // Perform a binary search
    while( first <= last ){
        a = &array[middle];

        if ( a->key < search ){
            first = middle + 1;
        } else if ( a->key == search ){
            return a->value;
        } else {
            // Check for overflow
            if (middle > INT_MAX - 1){ return -1;}
            last = middle - 1;
        }

        middle = (first + last) / 2;
    }

    // We didn't find the number
    if ( first > last ){ return -1;}

    // Shouldn't happen
    printf("ERROR: Binary search failed. Bug in code or malformed data?\n");
    return -1;
}



struct search_element * generate_table(struct record *records, unsigned long num_lines, unsigned long * unique_size, int record_location, signed int divisor_location){

    float * tmp_sort  = malloc(num_lines * sizeof(float));
    unsigned long num_valid_tmp = 0;

    // Copy the values to a temporary array in which to sort them
    for (int x=0; x<num_lines; x++){
        struct record *a_record = &records[x];
        if (a_record->float_records[record_location] != -1){
            if (divisor_location == -1){
                tmp_sort[num_valid_tmp] = a_record->float_records[record_location];
            } else {
                if ((a_record->float_records[divisor_location] == 0) || (a_record->float_records[divisor_location] == -1)){
                    tmp_sort[num_valid_tmp] = -1;
                    num_valid_tmp--;
                } else {
                    float tmp_holder = a_record->float_records[record_location]/a_record->float_records[divisor_location];
                    tmp_sort[num_valid_tmp] = roundf(tmp_holder * 10000)/100;
                }
            }
            num_valid_tmp++;
        }
    }

    // Sort the new values
    qsort(tmp_sort, num_valid_tmp, sizeof(float), sort_float);

    // Create a new array of structs for the unique records
    struct search_element * tmp_percentile = generate_search_field(tmp_sort, &num_valid_tmp);
    free(tmp_sort);

    *unique_size = num_valid_tmp;
    return tmp_percentile;
}

void print_percentile_table(struct search_element * percentiles, unsigned long num_elements, unsigned long print_element, int last){

    if (print_element < num_elements){
        struct search_element * a_rec = &percentiles[print_element];
        if (last){
            fprintf(stderr, "%f,%d\n", a_rec->key, a_rec->num_values);
        } else {
            fprintf(stderr, "%f,%d,", a_rec->key, a_rec->num_values);
        }
    } else {
        if (last){
            fprintf(stderr, "-1,-1\n");
        } else {
            fprintf(stderr, "-1,-1,");
        }
    }
}

// Replace a character in a string
char *replace(char *s, char old, char new){
    char *p = s;

    while(*p){
        if(*p == old) *p = new;

        ++p;
    }

    return s;
}

int main(int argc, char *argv[]){

    // Variables that we will use
    unsigned long num_lines;

    // Read in the file specified on the command line
    struct record *records = parse_file(argv[1], &num_lines);

    // Sort the data arrays
    unsigned long num_valid_cbeta_outlier, num_valid_rota_less1pct, num_valid_ramaoutlier, num_valid_pct_badbonds, num_valid_pct_badangles, num_valid_clashscore, num_valid_numpperp_outlier, num_valid_numsuite_outlier, num_valid_molprobityscore;
    struct search_element * cbeta_outlier_percentile, * rota_less1pct_percentile, * ramaoutlier_percentile, * pct_badbonds_percentile, * pct_badangles_percentile, * clashscore_percentile, * numpperp_outlier_percentile, * numsuite_outlier_percentile, * molprobityscore_percentile;

    //[['cbeta_outlier','numcbeta'], ['rota_less1pct','numrota'], ['ramaoutlier','numrama'], ['pct_badbonds'],['pct_badangles'],['clashscore'], ['numpperp_outlier', 'numpperp'], ['numsuite_outlier', 'numsuite']]

    cbeta_outlier_percentile = generate_table(records, num_lines, &num_valid_cbeta_outlier, cbeta_outlier_pos, numcbeta_pos);
    rota_less1pct_percentile = generate_table(records, num_lines, &num_valid_rota_less1pct, rota_less1pct_pos, numrota_pos);
    ramaoutlier_percentile = generate_table(records, num_lines, &num_valid_ramaoutlier, ramaoutlier_pos, numrama_pos);
    pct_badbonds_percentile = generate_table(records, num_lines, &num_valid_pct_badbonds, pct_badbonds_pos, -1);
    pct_badangles_percentile = generate_table(records, num_lines, &num_valid_pct_badangles, pct_badangles_pos, -1);
    clashscore_percentile = generate_table(records, num_lines, &num_valid_clashscore, clashscore_pos, -1);
    numpperp_outlier_percentile = generate_table(records, num_lines, &num_valid_numpperp_outlier, numpperp_outlier_pos, numpperp_pos);
    numsuite_outlier_percentile = generate_table(records, num_lines, &num_valid_numsuite_outlier, numsuite_outlier_pos, numsuite_pos);
    molprobityscore_percentile = generate_table(records, num_lines, &num_valid_molprobityscore, molprobityscore_pos, -1);

    // And lets print the distribution table on stderr
    for (int x=0; x<num_valid_clashscore; x++){
        fprintf(stderr, "%s,%s,%s,", argv[2], argv[3], argv[4]);
        print_percentile_table(cbeta_outlier_percentile, num_valid_cbeta_outlier, x, 0);
        print_percentile_table(rota_less1pct_percentile, num_valid_rota_less1pct, x, 0);
        print_percentile_table(ramaoutlier_percentile, num_valid_ramaoutlier, x, 0);
        print_percentile_table(pct_badbonds_percentile, num_valid_pct_badbonds, x, 0);
        print_percentile_table(pct_badangles_percentile, num_valid_pct_badangles, x, 0);
        print_percentile_table(clashscore_percentile, num_valid_clashscore, x, 0);
        print_percentile_table(numpperp_outlier_percentile, num_valid_numpperp_outlier, x, 0);
        print_percentile_table(numsuite_outlier_percentile, num_valid_numsuite_outlier, x, 0);
        print_percentile_table(molprobityscore_percentile, num_valid_molprobityscore, x, 1);
    }
    fclose(stderr);

    // Okay, now we are going to calculate the percentile table and print it
    for (unsigned long x=0; x<num_lines;x++){
        struct record *a_record = &records[x];

        printf("%s,%s,%s,%s,%s,%.0f,%f,%f,%f,%f,%f,%f,%f,%f,%f,%f,%f,%f,%f,%f,%f,%f,%f,%f,%f,%f,%f,%f,%f,%f,%f,%f,%f\n",
            argv[2], argv[3], argv[4], replace(a_record->text_records[macromolecule_types_pos], ',', '-'), a_record->text_records[pdb_pos], a_record->float_records[model_pos],

            calculate_percentile(cbeta_outlier_percentile, num_valid_cbeta_outlier, a_record->calculated_records[cbeta_normalized_pos]),
                a_record->calculated_records[cbeta_normalized_pos], a_record->float_records[cbeta_outlier_pos],

            calculate_percentile(rota_less1pct_percentile, num_valid_rota_less1pct, a_record->calculated_records[rota_normalized_pos]),
                a_record->calculated_records[rota_normalized_pos], a_record->float_records[rota_less1pct_pos],

            calculate_percentile(ramaoutlier_percentile, num_valid_ramaoutlier, a_record->calculated_records[rama_normalized_pos]),
                a_record->calculated_records[rama_normalized_pos], a_record->float_records[ramaoutlier_pos],

            calculate_percentile(pct_badbonds_percentile, num_valid_pct_badbonds, a_record->float_records[pct_badbonds_pos]),
                a_record->float_records[pct_badbonds_pos], a_record->float_records[numbadbonds_pos],

            calculate_percentile(pct_badangles_percentile, num_valid_pct_badangles, a_record->float_records[pct_badangles_pos]),
                a_record->float_records[pct_badangles_pos], a_record->float_records[numbadangles_pos],

            calculate_percentile(clashscore_percentile, num_valid_clashscore, a_record->float_records[clashscore_pos]),
                a_record->float_records[clashscore_pos], a_record->float_records[clashscore_pos],

            calculate_percentile(numpperp_outlier_percentile, num_valid_numpperp_outlier, a_record->calculated_records[pperp_normalized_pos]),
                a_record->calculated_records[pperp_normalized_pos], a_record->float_records[numpperp_outlier_pos],

            calculate_percentile(numsuite_outlier_percentile, num_valid_numsuite_outlier, a_record->calculated_records[suite_normalized_pos]),
                a_record->calculated_records[suite_normalized_pos], a_record->float_records[numsuite_outlier_pos],

            calculate_percentile(molprobityscore_percentile, num_valid_molprobityscore, a_record->float_records[molprobityscore_pos]),
                a_record->float_records[molprobityscore_pos], a_record->float_records[molprobityscore_pos]

                );
    }

    free(cbeta_outlier_percentile);
    free(rota_less1pct_percentile);
    free(ramaoutlier_percentile);
    free(pct_badbonds_percentile);
    free(pct_badangles_percentile);
    free(clashscore_percentile);
    free(numpperp_outlier_percentile);
    free(numsuite_outlier_percentile);
    free(molprobityscore_percentile);
    free(records);

    // All done
    return 0;
}
