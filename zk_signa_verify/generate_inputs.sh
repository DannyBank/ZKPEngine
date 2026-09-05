#!/bin/bash

input_file="inputs.txt"
output_file="Prover.toml"

# Extract value inside quotes, stripping trailing carriage returns (\r)
extract_value() {
    local key=$1
    grep "^$key\s*=" "$input_file" | sed -E 's/^[^=]+= *"(.*)"/\1/' | tr -d '\r'
}

# Convert hex string (without 0x) to quoted decimal byte array
hex_to_dec_quoted_array() {
    # Remove any 0x prefix and carriage returns/whitespace
    local hexstr=$(echo "$1" | sed 's/^0x//' | tr -d '\r ')
    local len=${#hexstr}
    local arr=()
    
    for (( i=0; i<len; i+=2 )); do
        local hexbyte="${hexstr:i:2}"
        # Skip if slice is empty or incomplete
        if [ ${#hexbyte} -eq 2 ]; then
            # Convert hex to decimal using printf (more resilient than 16#)
            local dec=$(printf "%d" "0x$hexbyte" 2>/dev/null)
            arr+=("\"$dec\"")
        fi
    done
    
    local joined=$(IFS=,; echo "${arr[*]}")
    echo "[$joined]"
}

# Read values from file
expected_address=$(extract_value expected_address)
hashed_message=$(extract_value hashed_message)
pub_key_x=$(extract_value pub_key_x)
pub_key_y=$(extract_value pub_key_y)
signature=$(extract_value signature)

# Strip 0x prefix if present
hashed_message=${hashed_message#0x}
pub_key_x=${pub_key_x#0x}
pub_key_y=${pub_key_y#0x}
signature=${signature#0x}

# Strip last byte (v) from signature (64 bytes / 128 hex chars remaining for r & s)
signature=${signature:0:128}

# Convert hex strings to decimal quoted arrays
hashed_message_arr=$(hex_to_dec_quoted_array "$hashed_message")
pub_key_x_arr=$(hex_to_dec_quoted_array "$pub_key_x")
pub_key_y_arr=$(hex_to_dec_quoted_array "$pub_key_y")
signature_arr=$(hex_to_dec_quoted_array "$signature")

# Write output
cat > "$output_file" <<EOF
expected_address = "$expected_address"
hashed_message = $hashed_message_arr
pub_key_x = $pub_key_x_arr
pub_key_y = $pub_key_y_arr
signature = $signature_arr
EOF

echo "Wrote $output_file"