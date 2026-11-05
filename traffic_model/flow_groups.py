import ast


def _eval(node, values):
    if isinstance(node, ast.Expression):
        return _eval(node.body, values)
    if isinstance(node, ast.Name):
        return values[node.id]
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = _eval(node.operand, values)
        return value if isinstance(node.op, ast.UAdd) else -value
    if isinstance(node, ast.BinOp) and isinstance(
        node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)
    ):
        a, b = _eval(node.left, values), _eval(node.right, values)
        return (
            a + b
            if isinstance(node.op, ast.Add)
            else a - b
            if isinstance(node.op, ast.Sub)
            else a * b
            if isinstance(node.op, ast.Mult)
            else a / b
        )
    raise ValueError("Unsupported formula syntax")


def resolve_flow_group(model, group_id, stack=()):
    if group_id in stack:
        raise ValueError("FlowGroup cycle: " + " -> ".join(stack + (group_id,)))
    g = model.flow_groups[group_id]
    if g.group_type == "base":
        return dict(model.matrices[g.matrix_id].values)
    if g.group_type == "component":
        result = {}
        for child, weight in g.components:
            for od, v in resolve_flow_group(model, child, stack + (group_id,)).items():
                result[od] = result.get(od, 0) + weight * v
        return result
    if g.group_type == "formula":
        names = {
            n.id
            for n in ast.walk(ast.parse(g.expression, mode="eval"))
            if isinstance(n, ast.Name)
        }
        matrices = {
            name: resolve_flow_group(model, name, stack + (group_id,)) for name in names
        }
        ods = set().union(*(x.keys() for x in matrices.values())) if matrices else set()
        return {
            od: _eval(
                ast.parse(g.expression, mode="eval"),
                {k: v.get(od, 0) for k, v in matrices.items()},
            )
            for od in ods
        }
    raise ValueError(f"Unknown FlowGroup type {g.group_type}")
