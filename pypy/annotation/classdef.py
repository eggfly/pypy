"""
Type inference for user-defined classes.
"""

from __future__ import generators
from pypy.annotation.model import SomeImpossibleValue, SomePBC, unionof
from pypy.annotation.model import SomeInteger, isdegenerated
from pypy.annotation import description


# The main purpose of a ClassDef is to collect information about class/instance
# attributes as they are really used.  An Attribute object is stored in the
# most general ClassDef where an attribute of that name is read/written:
#    classdef.attrs = {'attrname': Attribute()}
#
# The following invariants hold:
#
# (A) if an attribute is read/written on an instance of class A, then the
#     classdef of A or a parent class of A has an Attribute object corresponding
#     to that name.
#
# (I) if B is a subclass of A, then they don't both have an Attribute for the
#     same name.  (All information from B's Attribute must be merged into A's.)
#
# Additionally, each ClassDef records an 'attr_sources': it maps attribute names
# to a list of 'source' objects that want to provide a constant value for this
# attribute at the level of this class.  The attr_sources provide information
# higher in the class hierarchy than concrete Attribute()s.  It is for the case
# where (so far or definitely) the user program only reads/writes the attribute
# at the level of a subclass, but a value for this attribute could possibly
# exist in the parent class or in an instance of a parent class.
#
# The point of not automatically forcing the Attribute instance up to the
# parent class which has a class attribute of the same name is apparent with
# multiple subclasses:
#
#                                    A
#                                 attr=s1
#                                  /   \
#                                 /     \
#                                B       C
#                             attr=s2  attr=s3
#
# In this case, as long as 'attr' is only read/written from B or C, the
# Attribute on B says that it can be 's1 or s2', and the Attribute on C says
# it can be 's1 or s3'.  Merging them into a single Attribute on A would give
# the more imprecise 's1 or s2 or s3'.
#
# The following invariant holds:
#
# (II) if a class A has an Attribute, the 'attr_sources' for the same name is
#      empty.  It is also empty on all subclasses of A.  (The information goes
#      into the Attribute directly in this case.)
#
# The following invariant holds:
#
#  (III) for a class A, each attrsource that comes from the class (as opposed to
#        from a prebuilt instance) must be merged into all Attributes of the
#        same name in all subclasses of A, if any.  (Parent class attributes can
#        be visible in reads from instances of subclasses.)

class Attribute:
    # readonly-ness
    # SomeThing-ness
    # NB.  an attribute is readonly if it is a constant class attribute.
    #      Both writing to the instance attribute and discovering prebuilt
    #      instances that have the attribute set will turn off readonly-ness.

    def __init__(self, name, bookkeeper):
        self.name = name
        self.bookkeeper = bookkeeper
        self.s_value = SomeImpossibleValue()
        self.readonly = True
        self.read_locations = {}

    def add_constant_source(self, classdef, source):
        s_value = source.s_get_value(classdef, self.name)
        if source.instance_level:
            # a prebuilt instance source forces readonly=False, see above
            self.readonly = False
        s_new_value = unionof(self.s_value, s_value)       
        if isdegenerated(s_new_value):            
            self.bookkeeper.ondegenerated("source %r attr %s" % (source, self.name),
                                          s_new_value)
                
        self.s_value = s_new_value

    def getvalue(self):
        # Same as 'self.s_value' for historical reasons.
        return self.s_value

    def merge(self, other, classdef=None):
        assert self.name == other.name
        s_new_value = unionof(self.s_value, other.s_value)
        if isdegenerated(s_new_value):
            if classdef is None:
                what = "? attr %s" % self.name
            else:
                what = "%r attr %s" % (classdef, self.name)
            self.bookkeeper.ondegenerated(what, s_new_value)

        self.s_value = s_new_value        
        self.readonly = self.readonly and other.readonly
        self.read_locations.update(other.read_locations)

    def mutated(self, homedef): # reflow from attr read positions
        s_newvalue = self.getvalue()
        # check for method demotion
        if isinstance(s_newvalue, SomePBC):
            attr = self.name
            meth = False
            for desc in s_newvalue.descriptions:
                if isinstance(desc, description.MethodDesc):
                    meth = True
                    break
            if meth and homedef.classdesc.read_attribute(attr, None) is None:
                self.bookkeeper.warning("demoting method %s to base class %s" % (self.name, homedef))

        for position in self.read_locations:
            self.bookkeeper.annotator.reflowfromposition(position)        



class ClassDef:
    "Wraps a user class."

    def __init__(self, bookkeeper, classdesc):
        self.bookkeeper = bookkeeper
        self.attrs = {}          # {name: Attribute}
        self.classdesc = classdesc
        self.name = self.classdesc.name
        self.shortname = self.name.split('.')[-1]        
        self.subdefs = []
        self.attr_sources = {}   # {name: list-of-sources}

        if classdesc.basedesc:
            self.basedef = classdesc.basedesc.getuniqueclassdef()
            self.basedef.subdefs.append(self)
        else:
            self.basedef = None

        self.parentdefs = dict.fromkeys(self.getmro())

    def setup(self, sources):
        # collect the (supposed constant) class attributes
        for name, source in sources.items():
            self.add_source_for_attribute(name, source)
        if self.bookkeeper:
            self.bookkeeper.event('classdef_setup', self)

    def add_source_for_attribute(self, attr, source):
        """Adds information about a constant source for an attribute.
        """
        sources = self.attr_sources.setdefault(attr, [])
        for cdef in self.getmro():
            if attr in cdef.attrs:
                # the Attribute() exists already for this class (or a parent)
                attrdef = cdef.attrs[attr]
                s_prev_value = attrdef.s_value
                attrdef.add_constant_source(self, source)
                # we should reflow from all the reader's position,
                # but as an optimization we try to see if the attribute
                # has really been generalized
                if attrdef.s_value != s_prev_value:
                    attrdef.mutated(cdef) # reflow from all read positions
                return
        else:
            # remember the source in self.attr_sources
            sources.append(source)
            # register the source in any Attribute found in subclasses,
            # to restore invariant (III)
            # NB. add_constant_source() may discover new subdefs but the
            #     right thing will happen to them because self.attr_sources
            #     was already updated
            if not source.instance_level:
                for subdef in self.getallsubdefs():
                    if attr in subdef.attrs:
                        attrdef = subdef.attrs[attr]
                        s_prev_value = attrdef.s_value
                        attrdef.add_constant_source(self, source)
                        if attrdef.s_value != s_prev_value:
                            attrdef.mutated(subdef) # reflow from all read positions

    def locate_attribute(self, attr):
        while True:
            for cdef in self.getmro():
                if attr in cdef.attrs:
                    return cdef
            self.generalize_attr(attr)
            # the return value will likely be 'self' now, but not always -- see
            # test_annrpython.test_attr_moving_from_subclass_to_class_to_parent

    def find_attribute(self, attr):
        return self.locate_attribute(attr).attrs[attr]
    
    def __repr__(self):
        return "<ClassDef '%s'>" % (self.name,)

    def commonbase(self, other):
        other1 = other
        while other is not None and not self.issubclass(other):
            other = other.basedef
        # special case for MI with Exception
        #if other is None and other1 is not None:
        #    if issubclass(self.cls, Exception) and issubclass(other1.cls, Exception):
        #        return self.bookkeeper.getclassdef(Exception)
        return other

    #def superdef_containing(self, cls):
    #    clsdef = self
    #    while clsdef is not None and not issubclass(cls, clsdef.cls):
    #        clsdef = clsdef.basedef
    #    return clsdef

    def getmro(self):
        while self is not None:
            yield self
            self = self.basedef

    def issubclass(self, otherclsdef):
        return otherclsdef in self.parentdefs

    def getallsubdefs(self):
        pending = [self]
        seen = {}
        for clsdef in pending:
            yield clsdef
            for sub in clsdef.subdefs:
                if sub not in seen:
                    pending.append(sub)
                    seen[sub] = True

    def _generalize_attr(self, attr, s_value):
        # first remove the attribute from subclasses -- including us!
        # invariant (I)
        subclass_attrs = []
        constant_sources = []    # [(classdef-of-origin, source)]
        for subdef in self.getallsubdefs():
            if attr in subdef.attrs:
                subclass_attrs.append(subdef.attrs[attr])
                del subdef.attrs[attr]
            if attr in subdef.attr_sources:
                # accumulate attr_sources for this attribute from all subclasses
                lst = subdef.attr_sources[attr]
                for source in lst:
                    constant_sources.append((subdef, source))
                del lst[:]    # invariant (II)

        # accumulate attr_sources for this attribute from all parents, too
        # invariant (III)
        for superdef in self.getmro():
            if attr in superdef.attr_sources:
                for source in superdef.attr_sources[attr]:
                    if not source.instance_level:
                        constant_sources.append((superdef, source))

        # create the Attribute and do the generalization asked for
        newattr = Attribute(attr, self.bookkeeper)
        if s_value:
            newattr.s_value = s_value

        # keep all subattributes' values
        for subattr in subclass_attrs:
            newattr.merge(subattr, classdef=self)

        # store this new Attribute, generalizing the previous ones from
        # subclasses -- invariant (A)
        self.attrs[attr] = newattr

        # add the values of the pending constant attributes
        # completes invariants (II) and (III)
        for origin_classdef, source in constant_sources:
            newattr.add_constant_source(origin_classdef, source)

        # reflow from all read positions
        newattr.mutated(self)

    def generalize_attr(self, attr, s_value=None):
        # if the attribute exists in a superclass, generalize there,
        # as imposed by invariant (I)
        for clsdef in self.getmro():
            if attr in clsdef.attrs:
                clsdef._generalize_attr(attr, s_value)
                break
        else:
            self._generalize_attr(attr, s_value)

    def about_attribute(self, name):
        """This is the interface for the code generators to ask about
           the annotation given to a attribute."""
        for cdef in self.getmro():
            if name in cdef.attrs:
                s_result = cdef.attrs[name].s_value
                if s_result != SomeImpossibleValue():
                    return s_result
                else:
                    return None
        return None

    def lookup_filter(self, pbc, name=None):
        """Selects the methods in the pbc that could possibly be seen by
        a lookup performed on an instance of 'self', removing the ones
        that cannot appear.
        """
        d = []
        uplookup = None
        updesc = None
        meth = False
        check_for_missing_attrs = False
        for desc in pbc.descriptions:
            # pick methods but ignore already-bound methods, which can come
            # from an instance attribute
            if (isinstance(desc, description.MethodDesc)
                and desc.selfclassdef is None):
                meth = True
                methclassdef = desc.originclassdef
                if methclassdef is not self and methclassdef.issubclass(self):
                    pass # subclasses methods are always candidates
                elif self.issubclass(methclassdef):
                    # upward consider only the best match
                    if uplookup is None or methclassdef.issubclass(uplookup):
                        uplookup = methclassdef
                        updesc = desc
                    continue
                    # for clsdef1 >= clsdef2, we guarantee that
                    # clsdef1.lookup_filter(pbc) includes
                    # clsdef2.lookup_filter(pbc) (see formal proof...)
                else:
                    continue # not matching
                # bind the method by giving it a selfclassdef.  Use the
                # more precise subclass that it's coming from.
                desc = desc.bind_self(methclassdef)
            d.append(desc)
        if uplookup is not None:            
            # hack^2, in this case the classdef for uplookup could be the result
            # of the union of subclass sources that share the same implementation function
            # so there could be still super and subclass implementations added after the fact
            # that could be going undetected. We use uplookup.attr_sources[name] to flag
            # whether a super implementation was considered and as such not undetected
            if name is not None and not name in uplookup.attr_sources:
                uplookup.attr_sources.setdefault(name, [])
                check_for_missing_attrs = True

            # add the updesc method, bounding it to the more precise
            # classdef 'self' instead of its originclassdef
            d.append(updesc.bind_self(self))
        elif meth and name is not None:
            check_for_missing_attrs = True

        if check_for_missing_attrs:
            self.check_missing_attribute_update(name)

        if d or pbc.can_be_None:
            return SomePBC(d, can_be_None=pbc.can_be_None)
        else:
            return SomeImpossibleValue()

    def check_missing_attribute_update(self, name):
        # haaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaack
        # sometimes, new methods can show up on classes, added
        # e.g. by W_TypeObject._freeze_() -- the multimethod
        # implementations.  Check that here...
        found = False
        parents = list(self.getmro())
        parents.reverse()
        for base in parents:
            if base.check_attr_here(name):
                found = True
        return found

    def check_attr_here(self, name):
        source = self.classdesc.find_source_for(name)
        if source is not None:
            # oups! new attribute showed up
            self.add_source_for_attribute(name, source)
            # maybe it also showed up in some subclass?
            for subdef in self.getallsubdefs():
                if subdef is not self:
                    subdef.check_attr_here(name)
            return True
        else:
            return False

    def _freeze_(self):
        raise Exception, "ClassDefs are used as knowntype for instances but cannot be used as immutablevalue arguments directly"

# ____________________________________________________________

class InstanceSource:
    instance_level = True

    def __init__(self, bookkeeper, obj):
        self.bookkeeper = bookkeeper
        self.obj = obj
 
    def s_get_value(self, classdef, name):
        s_value = self.bookkeeper.immutablevalue(
            self.obj.__dict__[name])
        return s_value

# ____________________________________________________________

FORCE_ATTRIBUTES_INTO_CLASSES = {
    OSError: {'errno': SomeInteger()},
    }
