import re
import pathlib
import ast

root = pathlib.Path('frontend/ui')
for p in root.rglob('*.py'):
    txt = p.read_text(encoding='utf-8')

    def repl(m):
        raw = m.group(1)
        try:
            tup = ast.literal_eval(f'({raw})')
            if not isinstance(tup, tuple):
                tup = (tup,)
            family = tup[0] if len(tup) > 0 else 'Segoe UI'
            size = tup[1] if len(tup) > 1 else 12
            weight = 'bold' if len(tup) > 2 and 'bold' in str(tup[2]) else 'normal'
            return f"font=ctk.CTkFont(family='{family}', size={size}, weight='{weight}')"
        except Exception as exc:
            print(f'parse error in {p}: {raw} -> {exc}')
            return m.group(0)

    new = re.sub(r"font=\(([^\)]+)\)", repl, txt)
    if new != txt:
        p.write_text(new, encoding='utf-8')
        print('updated', p)
