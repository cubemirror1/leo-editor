#@+leo-ver=5-thin
#@+node:ekr.20160505094722.1: * @file importers/coffeescript.py
'''The @auto importer for coffeescript.'''
import re
import leo.core.leoGlobals as g
import leo.plugins.importers.linescanner as linescanner
Importer = linescanner.Importer
Target = linescanner.Target
new = False # True: use i.v2_scan_line (ctor follows protocol).
#@+others
#@+node:ekr.20160505094722.2: ** class CS_Importer(Importer)
class CS_Importer(Importer):

    #@+others
    #@+node:ekr.20160505101118.1: *3* coffee.__init__
    def __init__(self, importCommands, atAuto):
        '''Ctor for CoffeeScriptScanner class.'''
        Importer.__init__(self,
            importCommands,
            atAuto = atAuto,
            language = 'coffeescript',
            state_class = CS_ScanState,
                # Not used: This class overrides v2_scan_line.
            strict = True
        )
        self.errors = 0
        self.root = None
        self.tab_width = None
            # NOT the same as self.c.tabwidth.  Set in run().
    #@+node:ekr.20161113064226.1: *3* coffee.get_new_table
    #@@nobeautify

    def get_new_table(self, context):
        '''Return a new coffeescript state table for the given context.'''
        trace = False and not g.unitTesting

        def d(n):
            return 0 if context else n

        table = (
            # in-ctx: the next context when the pattern matches the line *and* the context.
            # out-ctx:the next context when the pattern matches the line *outside* any context.
            # deltas: the change to the indicated counts.  Always zero when inside a context.

            # kind,   pattern, out-ctx,  in-ctx, delta{}, delta(), delta[]
            ('len',   '\\\n',  context,   context,  0,       0,       0),
            ('len+1', '\\',    context,   context,  0,       0,       0),
            # Coffeedoc-style docstring.
            ('len',   '###',   '###',     '',       0,       0,       0),
            ('all',   '#',     '',        '',       0,       0,       0),
            ('len',   '"',     '"',       '',       0,       0,       0),
            ('len',   "'",     "'",       '',       0,       0,       0),
            ('len',   '{',     context,   context,  d(1),    0,       0),
            ('len',   '}',     context,   context,  d(-1),   0,       0),
            ('len',   '(',     context,   context,  0,       d(1),    0),
            ('len',   ')',     context,   context,  0,       d(-1),   0),
            ('len',   '[',     context,   context,  0,       0,       d(1)),
            ('len',   ']',     context,   context,  0,       0,       d(-1)),
        )
        if trace: g.trace('created table for coffescript state', repr(context))
        return table
    #@+node:ekr.20161110044000.2: *3* coffee.initial_state
    def initial_state(self):
        '''Return the initial counts.'''
        if new:
            # pylint: disable=no-value-for-parameter
            return CS_ScanState()
        else:
            return CS_ScanState('', 0)
    #@+node:ekr.20161108181857.1: *3* coffee.post_pass & helpers (revise)
    def post_pass(self, parent):
        '''Massage the created nodes.'''
        trace = False and not g.unitTesting and self.root.h.endswith('1.coffee')
        if trace:
            g.trace('='*60)
            for p in parent.self_and_subtree():
                print('***** %s' % p.h)
                g.printList(p.v._import_lines)
        # ===== Generic: use base Importer methods =====
        self.clean_all_headlines(parent)
        self.clean_all_nodes(parent)
        # ===== Specific to coffeescript =====
        #
        ### self.move_trailing_lines(parent)
        # ===== Generic: use base Importer methods =====
        self.unindent_all_nodes(parent)
        #
        # This sub-pass must follow unindent_all_nodes.
        self.promote_trailing_underindented_lines(parent)
        #
        # This probably should be the last sub-pass.
        self.delete_all_empty_nodes(parent)
        if trace:
            g.trace('-'*60)
            for p in parent.self_and_subtree():
                print('***** %s' % p.h)
                g.printList(p.v._import_lines)
    #@+node:ekr.20160505173347.1: *4* coffee.delete_trailing_lines
    def delete_trailing_lines(self, p):
        '''Delete the trailing lines of p.b and return them.'''
        body_lines, trailing_lines = [], []
        for s in g.splitLines(p.b):
            strip = s.strip()
            if not strip or strip.startswith('#'):
                trailing_lines.append(s)
            else:
                body_lines.extend(trailing_lines)
                body_lines.append(s)
                trailing_lines = []
        # Clear trailing lines if they are all blank.
        if all([not z.strip() for z in trailing_lines]):
            trailing_lines = []
        p.b = ''.join(body_lines)
        return trailing_lines
    #@+node:ekr.20160505170558.1: *4* coffee.move_trailing_lines
    def move_trailing_lines(self, parent):
        '''Move trailing lines into the following node.'''
        prev_lines = []
        last = None
        for p in parent.subtree():
            trailing_lines = self.delete_trailing_lines(p)
            if prev_lines:
                # g.trace('moving lines from', last.h, 'to', p.h)
                p.b = ''.join(prev_lines) + p.b
            prev_lines = trailing_lines
            last = p.copy()
        if prev_lines:
            # These should go after the @others lines in the parent.
            lines = g.splitLines(parent.b)
            for i, s in enumerate(lines):
                if s.strip().startswith('@others'):
                    lines = lines[:i+1] + prev_lines + lines[i+2:]
                    parent.b = ''.join(lines)
                    break
            else:
                # Fall back.
                last.b = last.b + ''.join(prev_lines)
    #@+node:ekr.20160505180032.1: *4* coffee.undent_coffeescript_body
    def undent_coffeescript_body(self, s):
        '''Return the undented body of s.'''
        trace = False and not g.unitTesting and self.root.h.endswith('1.coffee')
        lines = g.splitLines(s)
        if trace:
            g.trace('='*20)
            self.print_lines(lines)
        # Undent all leading whitespace or comment lines.
        leading_lines = []
        for line in lines:
            if self.is_ws_line(line):
                # Tricky.  Stipping a black line deletes it.
                leading_lines.append(line if line.isspace() else line.lstrip())
            else:
                break
        i = len(leading_lines)
        # Don't unindent the def/class line! It prevents later undents.
        tail = self.undent_body_lines(lines[i:], ignoreComments=True)
        # Remove all blank lines from leading lines.
        if 0:
            for i, line in enumerate(leading_lines):
                if not line.isspace():
                    leading_lines = leading_lines[i:]
                    break
        result = ''.join(leading_lines) + tail
        if trace:
            g.trace('-'*20)
            self.print_lines(g.splitLines(result))
        return result


    #@+node:ekr.20161110044000.3: *3* coffee.v2_scan_line (To do: use base class method)
    if new:
        
        pass
        
    else:

        def v2_scan_line(self, s, prev_state):
            '''Update the coffeescript scan state by scanning s.'''
            trace = False and not g.unitTesting
            context, indent = prev_state.context, prev_state.indent
            was_bs_nl = context == 'bs-nl'
            starts = None ### Not used. ### self.starts_def(s)
            ws = self.is_ws_line(s) and not was_bs_nl
            if was_bs_nl:
                context = '' # Don't change indent.
            else:
                indent = self.get_int_lws(s)
            i = 0
            while i < len(s):
                progress = i
                table = self.get_table(context)
                data = self.scan_table(context, i, s, table)
                context, i, delta_c, delta_p, delta_s, bs_nl = data
                # Only context and indent matter!
                assert progress < i
            if trace: g.trace(self, s.rstrip())
            return CS_ScanState(context, indent, starts=starts, ws=ws)
    #@+node:ekr.20161118134555.1: *3* COFFEE.v2_gen_lines & helpers
    def v2_gen_lines(self, s, parent):
        '''
        Non-recursively parse all lines of s into parent,
        creating descendant nodes as needed.
        '''
        trace = False and g.unitTesting
        prev_state = self.initial_state() ### CS_ScanState('', 0) ###
        target = Target(parent, prev_state)
        stack = [target, target]
        self.inject_lines_ivar(parent)
        for line in g.splitLines(s):
            new_state = self.v2_scan_line(line, prev_state)
            top = stack[-1]
            if trace: g.trace('(CS_Importer) line: %r\nnew_state: %s\ntop: %s' % (
                line, new_state, top))
            if self.is_ws_line(line):
                self.add_line(top.p, line)
            elif self.starts_block(line, prev_state):
                self.start_new_block(line, new_state, stack)
            elif new_state.indent >= top.state.indent:
                self.add_line(top.p, line)
            else:
                self.add_underindented_line(line, new_state, stack)
            prev_state = new_state
    #@+node:ekr.20161118134555.2: *4* COFFEE.add_underindented_line (Same as Python)
    def add_underindented_line(self, line, new_state, stack):
        '''
        Handle an unusual case: an underindented tail line.
        
        line is **not** a class/def line. It *is* underindented so it
        *terminates* the previous block.
        '''
        top = stack[-1]
        assert new_state.indent < top.state.indent, (new_state, top.state)
        # g.trace('='*20, '%s\nline: %r' % (g.shortFileName(self.root.h), repr(line)))
        self.cut_stack(new_state, stack)
        top = stack[-1]
        self.add_line(top.p, line)
        # Tricky: force section references for later class/def lines.
        if top.at_others_flag:
            top.gen_refs = True
    #@+node:ekr.20161118134555.3: *4* COFFEE.cut_stack (Same as Python)
    def cut_stack(self, new_state, stack):
        '''Cut back the stack until stack[-1] matches new_state.'''
        trace = False and g.unitTesting
        if trace:
            g.trace(new_state)
            g.printList(stack)
        assert len(stack) > 1 # Fail on entry.
        while stack:
            top_state = stack[-1].state
            if new_state.indent < top_state.indent:
                if trace: g.trace('new_state < top_state', top_state)
                assert len(stack) > 1, stack # <
                stack.pop()
            elif top_state.indent == new_state.indent:
                if trace: g.trace('new_state == top_state', top_state)
                assert len(stack) > 1, stack # ==
                stack.pop()
                break
            else:
                # This happens often in valid Python programs.
                if trace: g.trace('new_state > top_state', top_state)
                break
        # Restore the guard entry if necessary.
        if len(stack) == 1:
            if trace: g.trace('RECOPY:', stack)
            stack.append(stack[-1])
        assert len(stack) > 1 # Fail on exit.
        if trace: g.trace('new target.p:', stack[-1].p.h)
    #@+node:ekr.20161118134555.6: *4* COFFEE.start_new_block
    def start_new_block(self, line, new_state, stack):
        '''Create a child node and update the stack.'''
        # pylint: disable=arguments-differ
        trace = False and g.unitTesting
        assert not new_state.in_context(), new_state
        top = stack[-1]
        ### prev_p = top.p.copy()
        if trace:
            g.trace('line', repr(line))
            g.trace('top_state', top.state)
            g.trace('new_state', new_state)
            g.printList(stack)
        # Adjust the stack.
        if new_state.indent > top.state.indent:
            pass
        elif new_state.indent == top.state.indent:
            stack.pop()
        else:
            self.cut_stack(new_state, stack)
        # Create the child.
        top = stack[-1]
        parent = top.p
        self.gen_refs = top.gen_refs
        h = self.v2_gen_ref(line, parent, top)
        child = self.v2_create_child_node(parent, line, h)
        stack.append(Target(child, new_state))
        # Handle previous decorators.
        ### new_p = stack[-1].p.copy()
        ### self.move_decorators(new_p, prev_p)
    #@+node:ekr.20161118134555.7: *4* COFFEE.starts_block
    pattern_table = [
        re.compile(r'^\s*class'),
        re.compile(r'^\s*(.+):(.*)->'),
        re.compile(r'^\s*(.+)=(.*)->'),
    ]

    def starts_block(self, line, prev_state):
        '''True if the line starts with the patterns above outside any context.'''
        if prev_state.in_context():
            return False
        for pattern in self.pattern_table:
            if pattern.match(line):
                # g.trace('='*10, repr(line))
                return True
        return False
     
    #@-others
#@+node:ekr.20161110045131.1: ** class CS_ScanState
class CS_ScanState:
    '''A class representing the state of the v2 scan.'''
    
    if new:
        
        def __init__(self, indent=None, prev=None, s=None):
            '''Ctor for the ScanState class, used by i.general_scan_line.'''
            if prev:
                assert indent is not None
                assert s is not None
                self.indent = indent ### NOT prev.indent
                self.context = prev.context
                self.curlies = prev.curlies
                self.parens = prev.parens
                self.squares = prev.square
            else:
                self.bs_nl = False
                self.context = ''
                self.starts = self.ws = False
    
    else:
    
        def __init__(self, context, indent, starts=False, ws=False):
            '''CS_State ctor.'''
            assert isinstance(indent, int), (repr(indent), g.callers())
            self.bs_nl = False ### New ###
            self.context = context
            self.indent = indent
            self.starts = starts
            self.ws = ws # whitespace line, possibly ending in a comment.

    #@+others
    #@+node:ekr.20161118064325.1: *3* cs_state.__repr__
    def __repr__(self):
        '''CS_State.__repr__'''
        return '<CSState %r indent: %s starts: %s ws: %s>' % (
            self.context, self.indent, int(self.starts), int(self.ws))

    __str__ = __repr__
    #@+node:ekr.20161110045131.2: *3* cs_state.comparisons
    def __eq__(self, other):
        '''Return True if the state continues the previous state.'''
        return self.context or self.indent == other.indent

    def __lt__(self, other):
        '''Return True if we should exit one or more blocks.'''
        return not self.context and self.indent < other.indent

    def __gt__(self, other):
        '''Return True if we should enter a new block.'''
        return not self.context and self.indent > other.indent

    def __ne__(self, other): return not self.__eq__(other)

    def __ge__(self, other): return self > other or self == other

    def __le__(self, other): return self < other or self == other
    #@+node:ekr.20161110045131.3: *3* cs_state.v2_starts/continues_block
    def v2_continues_block(self, prev_state):
        '''Return True if the just-scanned line continues the present block.'''
        if prev_state.starts:
            # The first line *after* the class or def *is* in the block.
            prev_state.starts = False
            return True
        else:
            return self == prev_state or self.ws

    def v2_starts_block(self, prev_state):
        '''Return True if the just-scanned line starts an inner block.'''
        return not self.context and self.starts and self >= prev_state
    #@+node:ekr.20161118140100.1: *3* cs_state.in_context
    def in_context(self):
        '''True if in a special context.'''
        return (
            self.context or
            ###
            # self.curlies > 0 or
            # self.parens > 0 or
            # self.squares > 0 or
            self.bs_nl
        )
    #@-others
#@-others
importer_dict = {
    'class': CS_Importer,
    'extensions': ['.coffee', ],
}
#@-leo
