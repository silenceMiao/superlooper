import re


class SchemaValidationError(Exception):
    pass


class SchemaValidator:
    def validate(self, value, schema, path):
        errors = []
        self._validate(value, schema, path, errors)
        return errors

    def _validate(self, value, schema, path, errors):
        if not isinstance(schema, dict):
            errors.append(f"{path} schema 必须是 object。")
            return

        if "type" in schema and not self._matches_type(value, schema["type"]):
            errors.append(f"{path} 类型必须为 {self._type_label(schema['type'])}。")
            return

        if "const" in schema and not self._json_equal(value, schema["const"]):
            errors.append(f"{path} 必须为常量 {schema['const']!r}。")
        if "enum" in schema and not any(self._json_equal(value, option) for option in schema["enum"]):
            errors.append(f"{path} 值不在允许枚举中：{value!r}。")

        if "allOf" in schema:
            for child in schema["allOf"]:
                self._validate(value, child, path, errors)

        if "not" in schema and self._is_valid(value, schema["not"], path):
            errors.append(f"{path} 不得匹配禁止约束。")

        if "oneOf" in schema:
            matched = sum(self._is_valid(value, child, path) for child in schema["oneOf"])
            if matched != 1:
                errors.append(f"{path} 必须且只能匹配一个 oneOf 约束。")

        if "if" in schema:
            branch = schema.get("then") if self._is_valid(value, schema["if"], path) else schema.get("else")
            if branch is not None:
                self._validate(value, branch, path, errors)

        if isinstance(value, str):
            self._validate_string(value, schema, path, errors)
        if isinstance(value, list):
            self._validate_array(value, schema, path, errors)
        if isinstance(value, dict):
            self._validate_object(value, schema, path, errors)
        if self._is_integer(value):
            minimum = schema.get("minimum")
            if minimum is not None and value < minimum:
                errors.append(f"{path} 必须不小于 {minimum}。")

    def _validate_string(self, value, schema, path, errors):
        minimum = schema.get("minLength")
        if minimum is not None and len(value) < minimum:
            errors.append(f"{path} 长度必须不少于 {minimum}。")
        pattern = schema.get("pattern")
        if pattern is not None:
            try:
                matched = re.search(pattern, value)
            except re.error as exc:
                raise SchemaValidationError(f"{path} schema.pattern 无效：{exc}") from exc
            if not matched:
                errors.append(f"{path} 不匹配模式 {pattern!r}。")

    def _validate_array(self, value, schema, path, errors):
        minimum = schema.get("minItems")
        if minimum is not None and len(value) < minimum:
            errors.append(f"{path} 项数必须不少于 {minimum}。")
        item_schema = schema.get("items")
        if item_schema is not None:
            for index, item in enumerate(value):
                self._validate(item, item_schema, f"{path}[{index}]", errors)

    def _validate_object(self, value, schema, path, errors):
        minimum = schema.get("minProperties")
        if minimum is not None and len(value) < minimum:
            errors.append(f"{path} 属性数必须不少于 {minimum}。")

        properties = schema.get("properties", {})
        if not isinstance(properties, dict):
            raise SchemaValidationError(f"{path} schema.properties 必须是 object。")
        required = schema.get("required", [])
        if not isinstance(required, list):
            raise SchemaValidationError(f"{path} schema.required 必须是数组。")
        for name in required:
            if name not in value:
                errors.append(f"{path} 缺少必填字段：{name}。")
        for name, item in value.items():
            item_path = f"{path}.{name}"
            if name in properties:
                self._validate(item, properties[name], item_path, errors)
                continue
            additional = schema.get("additionalProperties", True)
            if additional is False:
                errors.append(f"{path} 存在未声明字段：{name}。")
            elif isinstance(additional, dict):
                self._validate(item, additional, item_path, errors)

        property_names = schema.get("propertyNames")
        if property_names is not None:
            for name in value:
                self._validate(name, property_names, f"{path} 属性名 {name!r}", errors)

    def _is_valid(self, value, schema, path):
        return not self.validate(value, schema, path)

    def _matches_type(self, value, expected):
        options = expected if isinstance(expected, list) else [expected]
        return any(self._matches_single_type(value, option) for option in options)

    def _matches_single_type(self, value, expected):
        return {
            "object": isinstance(value, dict),
            "array": isinstance(value, list),
            "string": isinstance(value, str),
            "integer": self._is_integer(value),
            "boolean": isinstance(value, bool),
            "null": value is None,
        }.get(expected, False)

    def _is_integer(self, value):
        return isinstance(value, int) and not isinstance(value, bool)

    def _json_equal(self, left, right):
        return type(left) is type(right) and left == right

    def _type_label(self, expected):
        if isinstance(expected, list):
            return "/".join(expected)
        return str(expected)
