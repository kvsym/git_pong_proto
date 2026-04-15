from dataclasses import dataclass
import time
from queue import Queue
import abc
from enum import Enum
from typing import List, OrderedDict

# from transitions.extensions.nesting import NestedState

# import hrt_interfaces.rtr.rtr_pb2 as proto_rtr

'''
This module is a grab bag of experimental concepts, constants, and functions.
'''

def time_ms() -> int:
    return time.perf_counter_ns() // 1000000

@dataclass(frozen=True)
class _CoreTopics:
    '''
    This frozen dataclass is used to hold constant values common among
    all HRT Bridges.
    '''
    HEARTBEAT = 'hrt/heartbeat'
    ADMIN = 'hrt/admin'
    TASK_ATTEMPT = ADMIN + '/task_attempt'
    SYSTEM = ADMIN + '/system'
    DWM = 'dwm1001_listener'
CoreTopics = _CoreTopics()

@dataclass(frozen=True)
class _QueryableServices:
    '''
    Zenoh queryable resource names.
    '''
    BACKEND = 'backend'
    AGENT_UPDATE = BACKEND + '/agent_update'
    HRT_ADMIN = BACKEND + '/hrt_admin'
    TASK_MGMT = BACKEND + '/task_mgmt'
    BRIDGE_MGMT = BACKEND + '/bridge_mgmt'
    HRT_UPDATE = BACKEND + '/hrt_update'
QueryableServices = _QueryableServices()

'''
Dataclasses used for internal representations of different objects
required across the Human-Robot Teaming stack.
'''

@dataclass
class Vector3:
    # Representation of a point in 3D space
    x: float
    y: float
    z: float

@dataclass
class AgentInfo:
    # Internal representation of an agent
    agent_name: str
    curr_task: str
    location: Vector3

@dataclass
class NeighborEntry:
    # Used to keep track of neighbor updates
    agent_info: AgentInfo
    last_update: int

'''
The following dataclasses are associated with the RTR standard.
'''
@dataclass
class KeyValue:
    # Simple Key-Value structure that mimics ROS2 diagnostic_msgs/KeyValue
    key: str
    value: str

@dataclass
class Condition:
    # Represents a condition that is attached to a transition.
    name: str       # name of the method to use for the condition
    src: 'Task'        # source task
    dest: 'Task'       # destination task
    params: list[KeyValue]

class ConstructType(Enum):
    SEQ = 0
    # TODO: Change PAR to SPLIT - OWL-S concurrent execution concept
    PAR = 1
    CYCLIC = 2

@dataclass
class ControlConstruct:
    # This dataclass maintains the construction of a composite task.           
    cons_type: ConstructType    # Specifies what type of composition
    # Components are the Composite/Atomic tasks involved with this composite task
    components: list['Task']
    # The conditions required to connect tasks
    conditions: list[Condition]

@dataclass
class Task:
    '''
    Semantics for the Task dataclass:
        AtomicTask has an empty (None) control_construct field
        CompositeTask has a populated control_construct 
    '''
    task_name: str
    params: list[KeyValue]
    ctrl_construct: ControlConstruct

# def convert_task(task_pb) -> Task:
#     '''
#     This function takes a task described in Protobuf and converts it to the
#     internal dataclass.
#     '''
#     # If the pb has not ctrl_construct field, this is an Atomic Task.
#     if not task_pb.HasField("ctrl_construct"):
#         params = [ KeyValue(key_val.key, key_val.value) for key_val in task_pb.params ]
#         task = Task(task_pb.task_name, params, ctrl_construct=None)
#         return task
#     else:
#         components = []
#         # Unpack components recursively and add to the list
#         for comp_pb in task_pb.ctrl_construct.components:
#             components.append(convert_task(comp_pb))
#         # Unpack the conditions serially
#         conditions = []
#         for cond_pb in task_pb.ctrl_construct.conditions:
#             cond_params = [ KeyValue(key_val.key, key_val.value) for key_val in cond_pb.params ]
#             src_task = convert_task(cond_pb.src)
#             dest_task = convert_task(cond_pb.dest)
#             conditions.append(Condition(
#                 cond_pb.name,
#                 src_task,
#                 dest_task,
#                 cond_params
#             ))
#         cons_type = -1
#         if task_pb.ctrl_construct.cons_type == proto_rtr.ConstructType.SEQ:
#             cons_type = ConstructType.SEQ
#         elif task_pb.ctrl_construct.cons_type == proto_rtr.ConstructType.PAR:
#             cons_type = ConstructType.PAR
#         else:
#             cons_type = ConstructType.CYCLIC
        
#         params = [ KeyValue(key_val.key, key_val.value) for key_val in task_pb.params ]
#         task = Task(task_pb.task_name, params, ControlConstruct(cons_type, components, conditions))
#         return task
    

# def is_valid_task(task : Task, valid_tasks : List[str]):
#     '''
#     This function takes a Task, which is modeled as a hierarchical
#     finite state machine, and a dictionary of valid_tasks. It traverses
#     the structure to ensure that all tasks and conditions are
#     constructed correctly.
#     '''
#     if task.task_name in valid_tasks:
#         # Base case: this Task is already determined to be valid.
#         return True
#     else:
#         # If the Task is unknown, need to examine its internals.
#         if task.ctrl_construct:
#             # This task is a Composite of one or more other tasks.
#             for component_task in task.ctrl_construct.components:
#                 if not is_valid_task(component_task, valid_tasks):
#                     return False
#             # If there are conditions, make sure they use only valid tasks
#             # TODO: check the condition name existence too
#             if task.ctrl_construct.conditions:
#                 for cond in task.ctrl_construct.conditions:
#                     if not cond.src in valid_tasks and cond.dest:
#                         return False
#             # Since all components are valid, this new task is valid.
#             valid_tasks.append(task.task_name)
#             return True
#         # If we reach here, this is an invalid atomic task.
#         return False

# def get_all_state_names(states : OrderedDict[str,NestedState], names : List[str]):
#     for state_name, substate in states.items():
#         names.append(state_name)
#         if substate.states:
#             get_all_state_names(substate.states, names)

###
#   The following classes were experimental and not being developed at this time.
#   Commented for future consideration.
###
# class BridgeConsumer(abc.ABC):

#     @abc.abstractmethod
#     def consume_from(self, queue : Queue):
#         '''
#         Subclasses implement the consumption of an item from a bridge queue
#         '''

# class BaseTask:
#     '''
#     Generic task structure that needs to be subclassed to
#     have any functionality. BaseTasks are run in ThreadPoolExecutors.
#     '''
#     def __init__(self, name : str) -> None:
#         self._name = name
#         self._is_live = True

#     def run(self) -> None:
#         raise NotImplementedError

#     @property
#     def name(self):
#         return self._name
    
#     @property
#     def is_live(self):
#         return self._is_live
    
#     def set_not_live(self):
#         self._is_live = False

# class BridgeTask(BaseTask):
#     '''
#     A class that represents the task to send data from one 
#     system to another.
#     '''
#     def __init__(self, name, queue : Queue, consumer : BridgeConsumer) -> None:
#         super().__init__(name)
#         self._queue = queue
#         self._consumer = consumer
        
#     def run(self) -> None:
#         while self._is_live:
#             self._consumer.consume_from(self._queue)