from typing import Optional, List, Dict, Any, Type, Union, Set
import re
import os
import logging
import hjson

from systemrdl import RDLCompiler, RDLImporter, Addrmap
from systemrdl import rdltypes
from systemrdl.messages import SourceRefBase
from systemrdl import component as comp
from systemrdl.rdltypes import AccessType, OnReadType, OnWriteType

from .typemaps import sw_from_access, hw_from_access


# Logger generation for halnode module
import_logger = logging.getLogger("import_logger")
# Console handler
ch = logging.StreamHandler()
# create formatter and add it to the handlers
formatter = logging.Formatter('%(name)s - %(levelname)s: %(message)s')
ch.setFormatter(formatter)
# add the handlers to the logger
import_logger.addHandler(ch)

# Set for more verbosity
import_logger.setLevel(logging.INFO)


class OpenTitanImporter(RDLImporter):

    def __init__(self, compiler: RDLCompiler):
        """
        Parameters
        ----------
        compiler:
            Reference to ``RDLCompiler`` instance to bind the importer to.
        """

        super().__init__(compiler)

        # Load extra signal properties to match more opentitan features
        props_path = os.path.join(os.path.dirname(__file__), "sig_props.rdl")
        self.compiler.compile_file(props_path)

    @property
    def src_ref(self) -> SourceRefBase:
        return self.default_src_ref


    def import_file(self, path: str, remap_state: Optional[str] = None) -> None:
        """
        Import a single OpenTitan HWJson file into the SystemRDL namespace.

        Parameters
        ----------
        path:
            Input OpenTitan HWJson file.
        """
        super().import_file(path)

        # tree = ElementTree.parse(path)
        tree = None
        with open(path) as f:
            tree = hjson.load(f)

        self.regwidth = None
        self._regoffset = 0

        self.import_ip(tree)

    unsupported_addrmap_props = ["cip_id",
                        "bus_interfaces",
                        "revisions",
                        "design_spec",
                        "dv_doc",
                        "hw_checklist",
                        "sw_checklist",
                        "design_stage",
                        "dif_stage",
                        "verification_stage",
                        "notes",
                        "version",
                        "life_stage",
                        "commit_id",
                        "alert_list",
                        "expose_reg_if",
                        "inter_signal_list",
                        "no_auto_id_regs",
                        "no_auto_feat_regs",
                        "no_auto_alert_regs",
                        "reset_request_list",
                        "scan",
                        "scan_reset",
                        "scan_en",
                        "SPDX-License-Identifier",
                        "wakeup_list",
                        "countermeasure"
                        ]

    unsupported_reg_props = [
                        "alias_target",   #	optional	string	name of the register to apply the alias definition to.
                        "async",   #	optional	string	indicates the register must cross to a different clock domain before use. The value shown here should correspond to one of the module’s clocks.
                        "sync",   #	optional	string	indicates the register needs to be on another clock/reset domain.The value shown here should correspond to one of the module’s clocks.
                        "hwre",   #	optional	string	‘true’ if hardware uses ‘re’ signal, which is latched signal of software read pulse.
                        "regwen",   #	optional	string	if register is write-protected by another register, that register name should be given here. empty-string for no register write protection
                        "tags",   #	optional	string	tags for the register, following the format ‘tag_name:item1:item2…’
                        "shadowed",   #	optional	string	‘true’ if the register is shadowed
                        "update_err_alert",   #	optional	string	alert that will be triggered if this shadowed register has update error
                        "storage_err_alert",   #	optional	string	alert that will be triggered if this shadowed register has storage error
                        ]

    unsupported_field_props = [
                        "alias_target",   #	optional	string	name of the field to apply the alias definition to.
                        "tags",   #	optional	string	tags for the field, followed by the format ‘tag_name:item1:item2…’
                        "mubi",   #	optional	bitrange	boolean flag for whether the field is a multi-bit type
                        "auto_split",   #	optional	bitrange	boolean flag which determines whether the field should be automatically separated into 1-bit sub-fields.This flag is used as a hint for automatically generated software headers with register description.
                        ]

    unsupported_signal_props = [
                        "type",   #	optional	string	name of the field to apply the alias definition to.
                        "default",   #	optional	string	tags for the field, followed by the format ‘tag_name:item1:item2…’
                        ]

    def warn_unsupported(self, key: str, tree: Dict, scope: Optional[str]):
        if key in tree:
            self.msg.warning(f"{scope} unsupported key: {key}", self.src_ref)

    def import_ip(self, tree: Dict ) -> None:
        for prop in OpenTitanImporter.unsupported_addrmap_props:
            self.warn_unsupported(prop, tree, "Addrmap")

        # Check for required values
        name = tree['name']
        if not name:
            self.msg.fatal("memoryMap is missing required tag 'name'", self.src_ref)

        # Create named component definition
        C_def = self.create_addrmap_definition(name)

        if 'human_name' in tree:
            self.assign_property(C_def, "name", tree['human_name'])
        else:
            self.assign_property(C_def, "name", tree['name'])

        if 'one_paragraph_desc' in tree:
            self.assign_property(C_def, "desc", tree['one_paragraph_desc'])
        elif 'one_line_desc' in tree:               # Use one_paragraph_desc if both set
            self.assign_property(C_def, "desc", tree['one_line_desc'])

        self.add_signals(C_def, tree)

        if 'regwidth' in tree:
            self.regwidth = int(tree['regwidth'])
        else:
            self.regwidth = 32 # Default for regtool is 32

        self.param_list = tree['param_list']

        self.add_registers(C_def, tree)

        self.register_root_component(C_def)

    def create_signal_definition(self, type_name: Optional[str] = None, src_ref: Optional[SourceRefBase] = None) -> comp.Signal:
        """
        Parameters
        ----------
        type_name: str
        src_ref: :class:`~SourceRefBase`

        Returns
        -------
        :class:`~comp.Signal`
            Component definition
        """
        return self._create_definition(comp.Signal, type_name, src_ref)

    def instantiate_signal(self, comp_def: comp.Signal, inst_name: str, src_ref: Optional[SourceRefBase] = None) -> comp.Signal:
        """
        Parameters
        ----------
        comp_def: :class:`comp.Signal`
        inst_name: str
        src_ref: :class:`~SourceRefBase`

        Returns
        -------
        :class:`~comp.Signal`
            Component instance
        """
        assert isinstance(comp_def, comp.Signal)
        return self._instantiate(comp_def, inst_name, src_ref)

    def add_signal_child(self, parent: comp.Component, child: comp.Signal) -> None:
        if not child.is_instance:
            raise ValueError("Child must be an instance if adding to a parent")

        parent.children.append(child)

    def add_signals(self, node : Addrmap, tree: Dict): # TODO FINISH

        # Add clock and reset
        list_type = "clocking"
        if list_type in tree:
            clocking = tree[list_type]
            for entry in clocking:
                for key, value in entry.items():
                    sig_dict = {'name': value}
                    if key == 'clock':
                        sig_dict['desc'] = "Input clock"
                        sig_dict['clock'] = True
                    elif key == 'reset':
                        sig_dict['reset_signal'] = True
                        if value == 'rst_ni':
                            sig_dict['desc'] = "Input reset, active low"
                            sig_dict['activelow'] = True
                        else:
                            sig_dict['desc'] = "Input reset, active high"
                            sig_dict['activehigh'] = True

                    S = self.create_signal(sig_dict, 'input')
                    self.add_signal_child(node, S)

        # Add inputs/outputs
        for sig_type in ['input', 'output', 'inout']:
            list_type = f'available_{sig_type}_list'

            if list_type in tree:
                for s in tree[list_type]:
                    S = self.create_signal(s, sig_type)
                    self.add_signal_child(node, S)

        # Add interrupts
        list_type = "interrupt_list"
        if list_type in tree:
            for s in tree[list_type]:
                S = self.create_signal(s, 'interrupt')
                self.add_signal_child(node, S)
        else:
            # If not existing create an empty list because
            # some checks are done later in the script
            tree["interrupt_list"] = []



    def create_signal(self, sig_dict : Dict, sig_type : str):
        for prop in OpenTitanImporter.unsupported_signal_props:
            self.warn_unsupported(prop, sig_dict, f"Signal {sig_dict['name']}")


        # Keep the opentitan port naming convention
        if sig_type == 'interrupt':
            signal_inst_name = f"intr_{sig_dict['name']}_o"
            # All interrupt are output signals
            sig_type = 'output'
        else:
            signal_inst_name = sig_dict['name']


        S = self.instantiate_signal(
                comp_def=self.create_signal_definition(sig_dict['name']),
                inst_name=signal_inst_name,
                )

        # Set the width to 1 if not defined
        if 'width' not in sig_dict:
            sig_dict['signalwidth'] = 1

        # Add signal type property to the signal dictionnary
        if sig_type not in sig_dict:
            sig_dict[sig_type] = True

        for prop in sig_dict:
            if self.compiler.env.property_rules.lookup_property(prop) is not None and prop != 'name':
                self.assign_property(S, prop, sig_dict[prop])


        return S

    def add_registers(self, node : Addrmap, tree: Dict):
        # Opentitan expect one register per interrupt
        # Check if any interrupt and if auto generated or not
        no_auto_intr_regs = tree['no_auto_intr_regs'] if 'no_auto_intr_regs' in tree else False
        if tree["interrupt_list"] and not no_auto_intr_regs in ['true', True]:
            # Check we have less than 32 interrupts
            assert len(tree["interrupt_list"]) <= 32, f"{tree['name']} module has more than 32 interrupts (not supported)."
            # Each interrupt requires 3 registers (of 1 bit)
            # 1. State register
            intr_state_reg = {'name': 'intr_state'}
            intr_state_reg['desc'] = "Interrupt state register."
            intr_state_reg['swaccess'] = 'rw1c'
            intr_state_reg['hwaccess'] = 'hrw'
            # 2. Enable register
            intr_enable_reg = {'name': 'intr_enable'}
            intr_enable_reg['desc'] = "Interrupt enable register."
            intr_enable_reg['swaccess'] = 'rw'
            intr_enable_reg['hwaccess'] = 'hro'
            # 3. Test register (no storage, only interface, sw read always returns 0)
            intr_test_reg = {'name': 'intr_test'}
            intr_test_reg['desc'] = "Interrupt test register."
            intr_test_reg['swaccess'] = 'wo'
            intr_test_reg['hwaccess'] = 'hro'
            intr_test_reg['hwext'] = 'true'
            # Interrupt test signal works using software write pulse ('hwqe' keyword)
            # As intr_test is external, the 'qe' signal can be reconstructed from
            # existing signals so no specific property is set

            intr_state_fields = []
            intr_enable_fields = []
            intr_test_fields = []

            # Generate the fields inside each register
            for cnt, intr in enumerate(tree["interrupt_list"]):
                intr_name = intr['name']
                desc = intr['desc']
                resval = intr['default'] if 'default' in intr else 0
                # Common to the 3 register fields
                base_field = {'name': intr_name,
                            'desc': desc,
                            'bits': str(cnt)}
                # State register fields can have a reset value
                status_field = base_field.copy()
                status_field['resval'] = resval
                # State register fields can have a reset value
                test_field = base_field.copy()
                # test_field['singlepulse'] = True
                # Add the new field
                intr_state_fields.append(status_field)
                intr_enable_fields.append(base_field)
                intr_test_fields.append(test_field)

            intr_state_reg['fields'] = intr_state_fields
            intr_enable_reg['fields'] = intr_enable_fields
            intr_test_reg['fields'] = intr_test_fields
            intr_regs = {'registers': [intr_state_reg, intr_enable_reg, intr_test_reg]}

            for reg in intr_regs['registers']:
                R = self.create_register(reg, self._regoffset)
                self._regoffset += self.regwidth//8
                # Update the offset for the next register
                self.add_child(node, R)

        # Add the explicit registers
        for reg in tree['registers']:
            if "multireg" in reg:
                multireg_dict = reg['multireg']
                # Attempt to convert count to an integer
                try:
                    count = int(multireg_dict['count'])
                except ValueError:
                    try:
                        count = multireg_dict['count']
                        # Search for the dictionary with 'name' matching count
                        param_dict = next((d for d in self.param_list if d.get('name') == count), None)
                        # Get the value
                        count = int(param_dict['default'])
                    except ValueError:
                        raise ValueError(f"No parameter with name matching {count} was found.")

                # By default, multireg are compacted if only one field
                # Not support for now, but can be easily added
                if 'compact' not in multireg_dict and len(multireg_dict['fields']) > 1:
                    raise ValueError(f"Uncompacted multireg support not implemented.")
                # Use the multireg entry has base model
                if multireg_dict['cname'] == multireg_dict['name']:
                    reg_name = multireg_dict['name']
                else:
                    reg_name = multireg_dict['name'] + '_' + multireg_dict['cname']

                reg_dict = {
                    'name'    : reg_name,
                    'desc'    : multireg_dict['desc']
                }
                # Check if swaccess and hwaccess at the register level
                # It is optional as long as the field(s) provide these values
                if 'swaccess' in multireg_dict:
                    reg_dict['swaccess'] = multireg_dict['swaccess']
                if 'hwaccess' in multireg_dict:
                    reg_dict['hwaccess'] = multireg_dict['hwaccess']
                # Register write enable and external properties
                if 'hwqe' in multireg_dict:
                    reg_dict['hwqe'] = 'true'
                if 'hwext' in multireg_dict:
                    reg_dict['hwext'] = 'true'
                # Replicate the fields count times
                fields_expanded = self.replicate_and_offset_bits(multireg_dict['fields'], count)
                # fields_expanded = [fields for fields in multireg_dict['fields'] for _ in range(count)]
                # Add them to the reg_dict
                reg_dict['fields'] = fields_expanded
                # Create the register
                R = self.create_register(reg_dict, self._regoffset)
                # Update the offset for the next register
                self._regoffset += self.regwidth//8
                self.add_child(node, R)
            elif "skipto" in reg:
                # Next address is given by skipto
                skipto = reg['skipto']
                self._regoffset = int_value = int(skipto, 16)
                continue
            else:
                R = self.create_register(reg, self._regoffset)
                # Update the offset for the next register
                self._regoffset += self.regwidth//8
                self.add_child(node, R)

    def expand_fields(self, fields_tpl: Dict, count: int) -> Dict:
        """Field replication for multireg entries for bits not to overlap."""

    def replicate_and_offset_bits(self, fields_tpl: Dict, count: int) -> Dict:
        """Field replication for multireg entries for bits offset modification."""
        # Distinguish bewteen "2" and "3:0" values
        def parse_bits(bits):
            if ':' in bits:
                high, low = map(int, bits.split(':'))
            else:
                high = low = int(bits)
            return high, low

        replicated_list = []
        bit_offset = 0

        for i in range(count):
            for entry in fields_tpl:
                high, low = parse_bits(entry['bits'])
                offset_entry = entry.copy()
                offset_entry['bits'] = f"{high+bit_offset}:{low+bit_offset}"
                # Append the idx to the name (if it exists)
                if 'name' in offset_entry:
                    offset_entry['name'] += f"_{i}"
                replicated_list.append(offset_entry)
            bit_offset += max(parse_bits(entry['bits'])[0] for entry in fields_tpl) + 1


        return replicated_list

    def create_register(self, reg_dict: Dict, addr_offset: int) -> comp.Reg:
        for prop in OpenTitanImporter.unsupported_reg_props:
            self.warn_unsupported(prop, reg_dict, f"Register {reg_dict['name']}")

        R = self.instantiate_reg(
                comp_def=self.create_reg_definition(type_name=reg_dict['name'].lower()),
                inst_name=reg_dict['name'].lower(),
                addr_offset=addr_offset
                )

        self.assign_property(R, 'desc', reg_dict['desc'])

        swaccess = reg_dict['swaccess'] if 'swaccess' in reg_dict else None
        hwaccess = reg_dict['hwaccess'] if 'hwaccess' in reg_dict else None
        hwext = reg_dict['hwext'] if 'hwext' in reg_dict else None

        resval = self.hex_or_dec_to_dec(reg_dict['resval']) if 'resval' in reg_dict else 0

        # If the register is external, no storage element should be generated
        # This uses a fork of PeakRDL-systemrdl to be compatible with the systemrdl-compiler
        # because the main PeakRDL-systemrdl code forwards the register external value to the fields
        # which generates an error from the compiler
        if hwext in ['true', True]:
            R.external = True

        self.add_fields(R, reg_dict, swaccess, hwaccess, resval)

        return R

    def add_fields(self,
                   reg: comp.Reg,
                   reg_dict: Dict,
                   default_swaccess : "str|None" = None,
                   default_hwaccess : "str|None" = None,
                   reg_resval       : int = 0,
                   ):

        # This features is given at the register level on opentitant but
        # set at the field level here to comply with SystemRDL specifications
        hwqe = reg_dict['hwqe'] if 'hwqe' in reg_dict else None

        for cnt, field_dict in enumerate(reg_dict['fields']):

            if 'name' in field_dict:
                field_name = field_dict['name']
            else:
                field_name =  f"val{cnt}"  # TODO default name

            for prop in OpenTitanImporter.unsupported_field_props:
                self.warn_unsupported(prop, field_dict, f"Field {field_name}")

            # bits can be either a single value, e.g., "2", or a range, e.g., "3:2"
            bits = [int(part) for part in field_dict['bits'].split(':')]
            if len(bits) == 2:
                bit_offset = bits[1]
                bit_width = (bits[0] - bits[1]) + 1
            elif len(bits) == 1:
                bit_offset = bits[0]
                bit_width = 1
            else:
                assert False

            F = self.instantiate_field(
                    comp_def=self.create_field_definition(field_name.lower()),
                    inst_name=field_name.lower(),
                    bit_offset=bit_offset,
                    bit_width=bit_width,
                    )

            self.assign_property(F, 'desc', field_dict['desc']) if 'desc' in field_dict else None

            swaccess = field_dict['swaccess'] if 'swaccess' in field_dict else default_swaccess
            hwaccess = field_dict['hwaccess'] if 'hwaccess' in field_dict else default_hwaccess


            # Assign sw properties
            sw, onwrite, onread = sw_from_access(swaccess)

            self.assign_property(F, "sw", sw)

            self.assign_property(F, "onread", onread) if onread is not None else None
            self.assign_property(F, "onwrite", onwrite) if onwrite is not None else None


            # Assign hw properties
            hw, we,  = hw_from_access(hwaccess)

            self.assign_property(F, "hw", hw)
            # Check if field is actually a storage
            # Settings below do not implement a register in SystemRDL so it cannot have a we
            if not(swaccess == 'ro' and (hwaccess == 'hwo' or hwaccess == 'hro')):
                self.assign_property(F, "we", we) if we is not None else None

            # Assign reset value
            if 'resval' in field_dict:
                resval = field_dict['resval']
                if resval == 'x':
                    self.msg.warning(f"Unsupported resval value: {resval}, using 0 instead")
                    resval = 0
                resval = self.hex_or_dec_to_dec(resval)
            else:
                # Use the reset value of the register if no field reset value
                resval = (reg_resval & ((2**bit_width-1) << bit_offset)) >> bit_offset

            self.assign_property(F, "reset", resval)

            # We use the swmod Systemrdl keyword to generate software access write pulse
            # Warning: swmod can also be assert depending on the onread property (see specs).
            if hwqe == 'true':
                self.assign_property(F, 'swmod', True)

            # Assign enums
            if 'enum' in field_dict:
                enum = self.parse_enum(field_dict)
                self.assign_property(F, "encode", enum)

            self.add_child(reg, F)

    def parse_enum(self, field_dict: Dict) -> Type[rdltypes.UserEnum]:

        members = []
        for enum in field_dict['enum']:
            if enum['name'][0].isdigit():
                self.msg.warning(f"Enumeration name cannot start with number: {enum['name']}, prepending underscore: _{enum['name']}")
                enum['name'] = "_" + enum['name']

            members.append(rdltypes.UserEnumMemberContainer(
                    name=enum['name'].lower(),
                    value=int(enum['value']),
                    rdl_name=None,
                    rdl_desc=enum['desc'],
                    ))

        enum_type = rdltypes.UserEnum.define_new(field_dict['name'].lower() + "_e", members)
        return enum_type

    def hex_or_dec_to_dec(self, num : "str|int"):
        if isinstance(num, str):
            if num.startswith("0x"):
                return int(num, 16)
            return int(num)
        else:
            return num
