"""List and filtered list model."""

# standard libraries
import copy
import operator
import re
import threading
import typing

# third party libraries
# None

# local libraries
from nion.utils import Observable
from nion.utils import Selection


class ListModel(Observable.Observable):

    def __init__(self, key: str, items=None):
        super().__init__()
        self.__key = key
        self.__items = list(items) if items else list()

    def insert_item(self, index: int, value) -> None:
        self.__items.insert(index, value)
        self.notify_insert_item(self.__key, value, index)

    def remove_item(self, index:int) -> None:
        value = self.__items[index]
        del self.__items[index]
        self.notify_remove_item(self.__key, value, index)

    @property
    def items(self):
        return self.__items

    def __getattr__(self, item):
        if item == self.__key:
            return self.items
        raise AttributeError()


class Filter:
    def __init__(self, default: bool=False):
        self.__default = default

    def __deepcopy__(self, memo):
        cls = self.__class__
        result = cls.__new__(cls)
        memo[id(self)] = result
        result.__default = self.__default
        return result

    def matches(self, d) -> bool:
        return self.__default


class AndFilter(Filter):
    def __init__(self, filters: typing.Sequence[Filter]=None):
        super().__init__()
        self.__filters = copy.copy(filters) if filters else list()

    def __deepcopy__(self, memo):
        result = super().__deepcopy__(memo)
        result.__filters = copy.deepcopy(self.__filters, memo)
        return result

    def matches(self, d) -> bool:
        return all(map(operator.methodcaller('matches', d), self.__filters))


class OrFilter(Filter):
    def __init__(self, filters: typing.Sequence[Filter]=None):
        super().__init__()
        self.__filters = copy.copy(filters) if filters else list()

    def __deepcopy__(self, memo):
        result = super().__deepcopy__(memo)
        result.__filters = copy.deepcopy(self.__filters, memo)
        return result

    def matches(self, d) -> bool:
        return any(map(operator.methodcaller('matches', d), self.__filters))


class NotFilter(Filter):
    def __init__(self, filter: Filter):
        super().__init__()
        self.__filter = filter

    def __deepcopy__(self, memo):
        result = super().__deepcopy__(memo)
        result.__filter = copy.deepcopy(self.__filter, memo)
        return result

    def matches(self, d) -> bool:
        return not self.__filter.matches(d)


class EqFilter(Filter):
    def __init__(self, key: str, value, cmp=None):
        super().__init__()
        self.__key = key
        self.__value = value
        self.__cmp = cmp if cmp else operator.eq

    def __deepcopy__(self, memo):
        result = super().__deepcopy__(memo)
        result.__key = self.__key
        result.__value = self.__value
        result.__cmp = self.__cmp
        return result

    def matches(self, d) -> bool:
        d_value = getattr(d, self.__key)
        return self.__cmp(d_value, self.__value)


class NotEqFilter(Filter):
    def __init__(self, key: str, value, cmp=None):
        super().__init__()
        self.__key = key
        self.__value = value
        self.__cmp = cmp if cmp else operator.eq

    def __deepcopy__(self, memo):
        result = super().__deepcopy__(memo)
        result.__key = self.__key
        result.__value = self.__value
        result.__cmp = self.__cmp
        return result

    def matches(self, d) -> bool:
        d_value = getattr(d, self.__key)
        return not self.__cmp(d_value, self.__value)


class StartsWithFilter(Filter):
    def __init__(self, key: str, value: str):
        super().__init__()
        self.__key = key
        self.__value = value

    def __deepcopy__(self, memo):
        result = super().__deepcopy__(memo)
        result.__key = self.__key
        result.__value = self.__value
        return result

    def matches(self, d) -> bool:
        d_value = getattr(d, self.__key)
        return d_value.startswith(self.__value)


class TextFilter(Filter):
    def __init__(self, key: str, text: str):
        super().__init__()
        self.__key = key
        self.__text = text

    def __deepcopy__(self, memo):
        result = super().__deepcopy__(memo)
        result.__key = self.__key
        result.__text = self.__text
        return result

    def matches(self, d) -> bool:
        d_value = getattr(d, self.__key)
        return re.search(self.__text, d_value, re.IGNORECASE) is not None


class PartialDateFilter(Filter):
    def __init__(self, key: str, year: int=None, month: int=None, day: int=None):
        super().__init__()
        self.__key = key
        self.__year = year
        self.__month = month
        self.__day = day

    def __deepcopy__(self, memo):
        result = super().__deepcopy__(memo)
        result.__key = self.__key
        result.__year = self.__year
        result.__month = self.__month
        result.__day = self.__day
        return result

    def matches(self, d) -> bool:
        d_value = getattr(d, self.__key)
        if self.__year and d_value.year != self.__year:
            return False
        if self.__month and d_value.month != self.__month:
            return False
        if self.__day and d_value.day != self.__day:
            return False
        return True


class PredicateFilter(Filter):
    # used for testing, not serializable
    def __init__(self, predicate):
        super().__init__()
        self.__predicate = predicate

    def __deepcopy__(self, memo):
        result = super().__deepcopy__(memo)
        result.__predicate = self.__predicate
        return result

    def matches(self, d) -> bool:
        return self.__predicate(d)


SortKeyCallable = typing.Callable


class FilteredListModel(Observable.Observable):
    """Filtered list of items.

    This class implements a filter function and a sorting function. Both the filter and
    sorting can be changed on the fly and this class will generate the appropriate insert
    and remove messages.

    Since changes can be slow, multiple changes are allowed to be made simultaneously by
    calling begin_change and end_change around the changes, or by using a context manager
    available via the changes method.
    """
    def __init__(self, *, items_key=None, container=None, selection=None):
        super().__init__()
        self.__items_key = items_key
        self.__container = None
        self.__master_items = list()  # a list of source items (to be filtered)
        self.__items = list()  # a list of filtered items
        self._update_mutex = threading.RLock()
        self.__filter = Filter(True)
        self.__sort_key = None
        self.__sort_reverse = False
        self.__change_level = 0
        self.__library_item_changed_event_listeners = dict()
        self.__item_inserted_event_listener = None
        self.__item_removed_event_listener = None
        self.__selections = list()
        if selection:
            self.__selections.append(selection)
        self.container = container

    def close(self):
        self.container = None
        self.__library_item_changed_event_listeners = None

    def begin_change(self):
        """ Begin a set of changes. Balance with end_changes. """
        self.__change_level += 1

    def end_change(self):
        """ End a set of changes and update items if finished. """
        with self._update_mutex:
            self.__change_level -= 1
            if self.__change_level == 0:
                self.__update_items()

    def changes(self):
        """ Acquire this while setting filter or sort so that changes get made simultaneously. """
        class ChangeTracker(object):  # pylint: disable=missing-docstring
            def __init__(self, binding):
                self.__binding = binding
            def __enter__(self):
                self.__binding.begin_change()
                return self
            def __exit__(self, type_, value, traceback):
                self.__binding.end_change()
        return ChangeTracker(self)

    # thread safe.
    @property
    def sort_key(self) -> SortKeyCallable:
        """ Return the sort key function (for item). """
        return self.__sort_key

    @sort_key.setter
    def sort_key(self, value: SortKeyCallable) -> None:
        """ Set the sort key function. """
        with self._update_mutex:
            self.__sort_key = value
        self.__update_items()

    @property
    def sort_reverse(self) -> bool:
        """ Return the sort reverse value. """
        return self.__sort_reverse

    @sort_reverse.setter
    def sort_reverse(self, value: bool) -> None:
        """ Set the sort reverse value. """
        with self._update_mutex:
            self.__sort_reverse = value
        self.__update_items()

    # thread safe.
    @property
    def filter(self) -> Filter:
        """ Return the filter function. """
        return self.__filter

    @filter.setter
    def filter(self, value: Filter) -> None:
        """ Set the filter function. """
        self.__filter = value
        self.__update_items()

    @property
    def items(self) -> typing.Sequence:
        """ Return the items. """
        with self._update_mutex:
            return copy.copy(self.__items)

    def __getattr__(self, item):
        if item == self.__items_key:
            return self.items
        raise AttributeError()

    # thread safe
    def _get_master_items(self):
        with self._update_mutex:
            return copy.copy(self.__master_items)

    def __find_sorted_index_for_item(self, item, items, sort_key, sort_operator):
        item_sort_key = sort_key(item)
        low = 0
        high = len(items)
        while low < high:
            mid = (low + high) // 2
            if sort_operator(sort_key(items[mid]), item_sort_key):
                low = mid + 1
            else:
                high = mid
        return low

    def __find_unsorted_index_for_item(self, item, master_items, filter):
        index = 0
        for item_ in master_items:
            if item_ == item:
                break
            if filter.matches(item_):
                index += 1
        return index

    # thread safe
    def __inserted_master_item(self, before_index, item):
        """
            Subclasses can call this to notify this object that a item in
            the master item list has been inserted.
        """
        with self._update_mutex:
            if self.__change_level > 0:
                return
            if self.filter.matches(item):
                items = self.__items
                sort_key = self.sort_key
                if sort_key is not None:
                    sort_operator = operator.gt if self.sort_reverse else operator.lt
                    before_index = self.__find_sorted_index_for_item(item, items, sort_key, sort_operator)
                else:
                    before_index = self.__find_unsorted_index_for_item(item, self._get_master_items(), self.filter)
                self.__items.insert(before_index, item)
                self.notify_insert_item(self.__items_key, item, before_index)

    # thread safe
    def __removed_master_item(self, index, item):
        """
            Subclasses can call this to notify this object that a item in
            the master item list has been removed.
        """
        with self._update_mutex:
            if self.__change_level > 0:
                return
            if item in self.__items:
                index = self.__items.index(item)
                assert self.__items[index] == item
                del self.__items[index]
                self.notify_remove_item(self.__items_key, item, index)

    # thread safe
    def __updated_master_item(self, item):
        """
            Subclasses can call this to notify this object that a item in
            the master item list has been updated.
        """
        with self._update_mutex:
            if self.__change_level > 0:
                return
            items = self.__items
            if self.filter.matches(item):
                # item will be in the list
                sort_key = self.sort_key
                if sort_key is not None:
                    # are items sorted?
                    sort_operator = operator.gt if self.sort_reverse else operator.lt
                    before_index = self.__find_sorted_index_for_item(item, items, sort_key, sort_operator)
                    if item in items:
                        # item already in list?
                        index = items.index(item)
                        if before_index < index:
                            self.__removed_master_item(index, item)
                            self.__inserted_master_item(before_index, item)
                        elif before_index > index:
                            self.__removed_master_item(index, item)
                            self.__inserted_master_item(before_index - 1, item)
                    else:
                        # item is not in list, just insert
                        self.__inserted_master_item(before_index, item)
                else:
                    # items are not sorted
                    if not item in items:
                        # item is not in list, just insert. the before_index we pass will not be used so just pass 0
                        self.__inserted_master_item(0, item)
            else:
                # item will not be in list
                if item in items:
                    # item already in list
                    index = items.index(item)
                    self.__removed_master_item(index, item)

    # thread safe.
    def __build_items(self):
        """Build the items from the master items list.

        This method is thread safe.

        Builds the items from the master list by sorting them and then
         filtering them.
        """
        master_items = self._get_master_items()
        assert len(set(master_items)) == len(master_items)
        # sort the master item list. this is optional since it may be sorted downstream.
        if self.sort_key is not None:
            master_items.sort(key=self.sort_key, reverse=self.sort_reverse)
        # construct the items list by expanding each master item to
        # include its children
        items = list()
        for item in master_items:
            # apply filter
            if self.filter.matches(item):
                # add item and its dependent items
                items.append(item)
        return items

    # thread safe.
    def __update_items(self):
        """Build the items and generate change messages.

        Builds the items from the master item list, then generates a sequence of
         inserter and remover calls representing the changes from the previous list.
        """
        with self._update_mutex:
            if self.__change_level > 0:
                return
            # first build the new items list, including items with master item.
            old_items = copy.copy(self.__items)
            items = self.__build_items()
            # now generate the insert/remove instructions to make the official
            # list match the proposed list.
            assert len(set(self._get_master_items())) == len(self._get_master_items())
            assert len(set(items)) == len(items)
            index = 0
            for item in items:
                # otherwise, if new item at current index is in old list, remove it, then re-insert
                if item in old_items:
                    old_index = old_items.index(item)
                    assert index <= old_index
                    # remove, re-insert, unless old and new position are the same
                    if index < old_index:
                        assert item in self.__items
                        del old_items[old_index]
                        del self.__items[old_index]
                        self.notify_remove_item(self.__items_key, item, old_index)
                        assert item not in self.__items
                        old_items.insert(index, item)
                        self.__items.insert(index, item)
                        self.notify_insert_item(self.__items_key, item, index)
                # else new item at current index is not in old list, insert it
                else:
                    assert item not in self.__items
                    old_items.insert(index, item)
                    self.__items.insert(index, item)
                    self.notify_insert_item(self.__items_key, item, index)
                index += 1
            # finally anything left in the old list can be removed
            while index < len(old_items):
                item_to_remove = old_items[index]
                assert item_to_remove in self.__items
                del old_items[index]
                del self.__items[index]
                self.notify_remove_item(self.__items_key, item_to_remove, index)

    # thread safe.
    @property
    def container(self):
        return self.__container

    # thread safe.
    @container.setter
    def container(self, container):
        if self.__container:
            self.__item_inserted_event_listener.close()
            self.__item_inserted_event_listener = None
            self.__item_removed_event_listener.close()
            self.__item_removed_event_listener = None
            for item in reversed(copy.copy(getattr(self.__container, self.__items_key))):
                self.__item_removed(self.__items_key, item, len(self._get_master_items()) - 1)
        self.__container = container
        if self.__container:
            self.__item_inserted_event_listener = self.__container.item_inserted_event.listen(self.__item_inserted)
            self.__item_removed_event_listener = self.__container.item_removed_event.listen(self.__item_removed)
            for index, item in enumerate(getattr(self.__container, self.__items_key)):
                self.__item_inserted(self.__items_key, item, index)

    def make_selection(self):
        selection = Selection.IndexedSelection()
        self.__selections.append(selection)
        return selection

    def release_selection(self, selection):
        self.__selections.remove(selection)

    # thread safe.
    def __item_inserted(self, key, item, before_index):
        """ Insert the item. Called from the container. """
        if key == self.__items_key:
            with self._update_mutex:
                assert not item in self.__master_items
                self.__master_items.insert(before_index, item)

                # thread safe
                def item_content_changed():
                    with self._update_mutex:
                        assert item in self.__master_items
                        self.__updated_master_item(item)

                self.__library_item_changed_event_listeners[id(item)] = item.item_changed_event.listen(item_content_changed)
                self.__inserted_master_item(before_index, item)
                for selection in self.__selections:
                    selection.insert_index(before_index)

    # thread safe.
    def __item_removed(self, key, item, index):
        """ Remove the item. Called from the container. """
        if key == self.__items_key:
            with self._update_mutex:
                del self.__master_items[index]
                self.__library_item_changed_event_listeners[id(item)].close()
                del self.__library_item_changed_event_listeners[id(item)]
                self.__removed_master_item(index, item)
                for selection in self.__selections:
                    selection.remove_index(index)