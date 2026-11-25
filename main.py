
import pandas as pd
import json
import re
from pathlib import Path


# --------------------------------------------------
# 1. Load validation configuration
# --------------------------------------------------

def load_rules(config_path):
    with open(config_path, "r", encoding="utf-8") as file:
        return json.load(file)


# --------------------------------------------------
# 2. Read CSV or Excel file
# --------------------------------------------------

def read_input_file(file_path):
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError("Input file not found.")

    extension = file_path.suffix.lower()

    if extension == ".csv":
        df = pd.read_csv(file_path, dtype=str)

    elif extension in [".xlsx", ".xls"]:
        df = pd.read_excel(file_path, dtype=str)

    else:
        raise ValueError("Only CSV and Excel files are supported.")

    # Convert missing values to empty strings
    df = df.fillna("")

    # Remove unnecessary spaces from column names
    df.columns = df.columns.str.strip()

    return df


# --------------------------------------------------
# 3. Check whether a value is empty
# --------------------------------------------------

def is_empty(value):
    return str(value).strip() == ""


# --------------------------------------------------
# 4. Email validation
# --------------------------------------------------

def validate_email(value):
    pattern = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
    return bool(re.match(pattern, str(value).strip()))


# --------------------------------------------------
# 5. Phone validation
# --------------------------------------------------

def validate_phone(value):
    value = str(value).strip()

    # Allow +, spaces, hyphens, and parentheses
    if not re.fullmatch(r"[+0-9\s()-]+", value):
        return False

    # Check digit count after removing formatting
    digits = re.sub(r"\D", "", value)

    return 10 <= len(digits) <= 15


# --------------------------------------------------
# 6. Validate a single field
# --------------------------------------------------

def validate_field(value, rules, column_name):
    errors = []

    value = str(value).strip()

    # Required field check
    if rules.get("required", False) and is_empty(value):
        errors.append(f"{column_name} is required")
        return errors

    # Skip remaining checks if optional field is empty
    if is_empty(value):
        return errors

    field_type = rules.get("type")

    # Email validation
    if field_type == "email":
        if not validate_email(value):
            errors.append("Invalid email format")

    # Phone validation
    elif field_type == "phone":
        if not validate_phone(value):
            errors.append("Invalid phone number")

    # Integer validation
    elif field_type == "integer":
        try:
            number = int(value)

            if "min" in rules and number < rules["min"]:
                errors.append(
                    f"Value must be at least {rules['min']}"
                )

            if "max" in rules and number > rules["max"]:
                errors.append(
                    f"Value must not exceed {rules['max']}"
                )

        except ValueError:
            errors.append("Must be a valid integer")

    # Float validation
    elif field_type == "number":
        try:
            number = float(value)

            if "min" in rules and number < rules["min"]:
                errors.append(
                    f"Value must be at least {rules['min']}"
                )

            if "max" in rules and number > rules["max"]:
                errors.append(
                    f"Value must not exceed {rules['max']}"
                )

        except ValueError:
            errors.append("Must be a valid number")

    # Allowed values validation
    if "allowed_values" in rules:
        allowed = rules["allowed_values"]

        if value not in allowed:
            errors.append(
                f"Must be one of: {', '.join(map(str, allowed))}"
            )

    return errors


# --------------------------------------------------
# 7. Validate all records
# --------------------------------------------------

def validate_records(df, config):
    errors_list = []

    # Duplicate validation settings
    duplicate_config = config.get("_duplicate_check", {})
    duplicate_columns = duplicate_config.get("columns", [])

    # Check whether duplicate columns exist
    for column in duplicate_columns:
        if column not in df.columns:
            raise ValueError(
                f"Duplicate check column '{column}' not found in file."
            )

    # Find all duplicate records based on selected columns
    if duplicate_columns:
        duplicate_mask = df.duplicated(
            subset=duplicate_columns,
            keep=False
        )
    else:
        duplicate_mask = pd.Series(False, index=df.index)

    # Validate every record
    for index, row in df.iterrows():
        record_errors = []

        # Validate each configured column
        for column, rules in config.items():

            # Skip special duplicate configuration
            if column.startswith("_"):
                continue

            # Check if the configured column exists
            if column not in df.columns:
                raise ValueError(
                    f"Configured column '{column}' not found in input file."
                )

            value = row[column]

            field_errors = validate_field(
                value,
                rules,
                column
            )

            for error in field_errors:
                record_errors.append(error)

        # Duplicate validation
        if duplicate_columns and duplicate_mask.loc[index]:
            record_errors.append(
                "Duplicate record based on columns: "
                + ", ".join(duplicate_columns)
            )

        errors_list.append("; ".join(record_errors))

    # Add error descriptions to DataFrame
    df["Validation_Errors"] = errors_list

    # Separate valid and invalid records
    valid_records = df[df["Validation_Errors"] == ""].copy()
    invalid_records = df[df["Validation_Errors"] != ""].copy()

    return valid_records, invalid_records


# --------------------------------------------------
# 8. Save output files
# --------------------------------------------------

def save_results(valid_records, invalid_records, output_folder):
    output_folder = Path(output_folder)
    output_folder.mkdir(parents=True, exist_ok=True)

    valid_path = output_folder / "valid_records.csv"
    invalid_path = output_folder / "invalid_records.csv"

    valid_records.to_csv(valid_path, index=False)
    invalid_records.to_csv(invalid_path, index=False)

    print("\nOutput files generated:")
    print(f"Valid records   : {valid_path}")
    print(f"Invalid records : {invalid_path}")


# --------------------------------------------------
# 9. Display summary
# --------------------------------------------------

def display_summary(total, valid_count, invalid_count):
    print("\n" + "=" * 40)
    print("         VALIDATION SUMMARY")
    print("=" * 40)

    print(f"Total records processed : {total}")
    print(f"Valid records          : {valid_count}")
    print(f"Invalid records        : {invalid_count}")

    if total > 0:
        failure_percentage = (invalid_count / total) * 100
        print(f"Failure percentage     : {failure_percentage:.2f}%")

    print("=" * 40)


# --------------------------------------------------
# 10. Main program
# --------------------------------------------------

def main():
    print("Employee Data Validation Tool")
    print("-" * 35)

    input_path = input("Enter CSV or Excel file path: ").strip()
    config_path = input("Enter validation JSON path: ").strip()
    output_folder = input("Enter output folder path: ").strip()

    try:
        # Load rules
        config = load_rules(config_path)

        # Read input
        df = read_input_file(input_path)

        total_records = len(df)

        # Validate data
        valid_records, invalid_records = validate_records(
            df, config
        )

        # Save results
        save_results(
            valid_records,
            invalid_records,
            output_folder
        )

        # Display summary
        display_summary(
            total_records,
            len(valid_records),
            len(invalid_records)
        )

    except Exception as e:
        print(f"\nError: {e}")


if __name__ == "__main__":
    main()
