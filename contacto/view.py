"""Module used for searching within the storage tree.

It creates induced subgraphs from the tree by filtering out elements.
These subgraphs may then be viewed as search results.
"""
import copy
from .helpers import DType, fmatch
from .storage import Group, Entity, Attribute


class View:
    """A read-only representation of a Storage slice.

    Provides a "groups" member that mimics that of the Storage object.
    Therefore the View itself is a read-only storage root and may be passed
    to contexts that do not modify the tree, such as serialization.

    To filter the tree, set your filters first using the provided methods.
    """

    def __init__(self, storage):
        """Initialize with a storage containing the full tree
        """
        self.source = storage.groups
        self.reset()

    def reset(self):
        """Resets the View back to the full tree, discarding any prior scoping.

        Also discards any set filters.
        """
        self.index_filters = [None, None, None]
        self.value_predicates = [None, None, None]
        self.groups = self.source

    def empty(self):
        """Tests if no filters have been set

        :return: True if no filters are set
        :rtype:  bool
        """
        return self.index_filters == [None, None, None] and \
            self.value_predicates == [None, None, None]

    def set_index_filters(self, filters):
        """Sets string needles that match exactly on an element's name.

        :param filters: parsed generic refspec (G/E/A)
        :type filters:  tuple
        """
        self.index_filters = [
            new_f or old_f
            for new_f, old_f in zip(filters, self.index_filters)
        ]

    def set_name_filters(self, filters):
        """Sets string needles that match fuzzily on an element's name.

        This means a case-insensitive substring search.
        Example: "abc" matches an element named "zAbcDeF"

        :param filters: parsed generic refspec (G/E/A)
        :type filters:  tuple
        """
        def sel(filt):
            if filt:
                return lambda x: fmatch(filt, x.name)
            return None

        preds = [sel(filt) for filt in filters]
        self.set_value_predicates(preds)

    def set_attr_value_filter(self, needle, fuzzy):
        """Sets a string needle that matches on a TEXT Attribute's value.

        Non-TEXT Attributes are not considered a match.
        May be specified both as exact and fuzzy search.
        An empty string is not considered a valid value filter.

        :param needle: search needle
        :type needle:  str
        :param fuzzy: use fuzzy search for the needle
        :type fuzzy:  bool
        """
        if not needle:
            return

        def pred(x):
            dtype, val = x.get()
            if dtype is not DType.TEXT:
                return False
            if fuzzy:
                return fmatch(needle, val)
            return needle == val

        self.set_value_predicates((None, None, pred))

    def set_value_predicates(self, preds):
        """Sets generic predicates that determine if an element is matched.

        Receives 3 predicates, one for each tree element type.
        This method may be called multiple times to stack multiple predicates
        on a single element. Stacked predicates are joined with logical AND.

        Example predicates:

        `L(attr): attr is binary`

        `L(entity): entity has thumbnail`

        :param preds: element predicates
        :type  preds: tuple
        """
        def join(new_p, old_p):
            if old_p and new_p:
                return lambda x: old_p(x) and new_p(x)
            return new_p or old_p

        self.value_predicates = [
            join(new_p, old_p)
            for new_p, old_p in zip(preds, self.value_predicates)
        ]

    def filter(self):
        """Generates an induced subgraph from the current tree
        using the saved filters
        """
        if self.empty():
            return
        ind_g, ind_e, ind_a = self.index_filters  # strings
        val_g, val_e, val_a = self.value_predicates  # predicates

        grps = {}
        iter_groups = self.groups
        # group index filter
        if ind_g:
            if ind_g not in iter_groups:
                self.groups = {}
                return
            iter_groups = {ind_g: iter_groups[ind_g]}
        for gname, group in iter_groups.items():
            # group value filter
            if val_g and not val_g(group):
                continue
            iter_entities = group.entities
            # entity index filter
            if ind_e:
                if ind_e not in iter_entities:
                    continue
                iter_entities = {ind_e: iter_entities[ind_e]}
            ents = {}
            for ename, entity in iter_entities.items():
                # entity value filter
                if val_e and not val_e(entity):
                    continue
                iter_attributes = entity.attributes
                # attribute index filter
                if ind_a:
                    if ind_a not in iter_attributes:
                        continue
                    iter_attributes = {ind_a: iter_attributes[ind_a]}
                attrs = {}
                for aname, attr in iter_attributes.items():
                    # attribute value filter
                    if val_a and not val_a(attr):
                        continue
                    attrs[aname] = copy.copy(attr)
                nofilt = len(iter_attributes) == 0 and not val_a
                if len(attrs) > 0 or nofilt:
                    ent = copy.copy(entity)
                    ent.attributes = attrs
                    for attr in attrs.values():
                        attr.parent = ent
                    ents[ename] = ent
            nofilt = len(iter_entities) == 0 and not (val_e or ind_a or val_a)
            if len(ents) > 0 or nofilt:
                grp = copy.copy(group)
                grp.entities = ents
                for ent in ents.values():
                    ent.parent = grp
                grps[gname] = grp
        self.groups = grps
