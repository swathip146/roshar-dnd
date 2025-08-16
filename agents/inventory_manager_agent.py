"""
Inventory Manager Agent
Handles item management, equipment, and inventory-related D&D mechanics
"""
import json
import os
from typing import Dict, List, Any, Optional
from agent_framework import BaseAgent

class InventoryManagerAgent(BaseAgent):
    """Agent for managing D&D character inventories and equipment"""
    
    def __init__(self, items_dir: str = "docs/items", inventory_dir: str = None, verbose: bool = False):
        super().__init__("inventory_manager", "inventory_manager")
        # Support both parameter names for compatibility
        self.items_dir = inventory_dir if inventory_dir is not None else items_dir
        self.item_database = {}
        self.character_inventories = {}
        self.verbose = verbose
        
        # Ensure items directory exists
        os.makedirs(self.items_dir, exist_ok=True)
        
        # Load item database
        self._load_item_database()
        
        # Add basic D&D items
        self._add_basic_items()
        
    def _setup_handlers(self):
        """Setup message handlers for this agent"""
        # Register message handlers
        self.register_handler("add_item", self._handle_add_item)
        self.register_handler("remove_item", self._handle_remove_item)
        self.register_handler("get_inventory", self._handle_get_inventory)
        self.register_handler("equip_item", self._handle_equip_item)
        self.register_handler("unequip_item", self._handle_unequip_item)
        self.register_handler("get_equipped_items", self._handle_get_equipped_items)
        self.register_handler("search_items", self._handle_search_items)
        self.register_handler("get_item_info", self._handle_get_item_info)
        self.register_handler("transfer_item", self._handle_transfer_item)
        self.register_handler("calculate_carrying_capacity", self._handle_calculate_carrying_capacity)
        self.register_handler("get_armor_class", self._handle_get_armor_class)
        self.register_handler("create_custom_item", self._handle_create_custom_item)
        self.register_handler("initialize_inventory", self._handle_initialize_inventory)
        self.register_handler("get_carrying_capacity", self._handle_get_carrying_capacity)
        self.register_handler("game_state_updated", self._handle_game_state_updated)
    
    def process_tick(self):
        """Process one tick/cycle of the agent's main loop"""
        # Inventory manager doesn't need active processing
        pass
    
    def handle_message(self, message):
        """Handle message - supports both AgentMessage objects and dict for testing"""
        if isinstance(message, dict):
            # For testing - convert dict to action and data
            action = message.get("action")
            data = message.get("data", {})
            handler = self.message_handlers.get(action)
            if handler:
                return handler(data)
            else:
                return {"success": False, "error": f"Unknown action: {action}"}
        else:
            # Normal AgentMessage handling
            return super().handle_message(message)
    
    def _handle_initialize_inventory(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Initialize inventory for a character"""
        try:
            character_name = message_data.get("character", "").strip().lower()
            strength_score = message_data.get("strength_score", 10)
            
            if not character_name:
                return {"success": False, "error": "Character name is required"}
            
            # Calculate carrying capacity based on strength
            carrying_capacity = strength_score * 15  # D&D 5e standard
            
            # Initialize character inventory
            self.character_inventories[character_name] = {
                "items": {},
                "equipped": {},
                "total_weight": 0.0,
                "carrying_capacity": carrying_capacity,
                "strength_score": strength_score
            }
            
            if self.verbose:
                print(f"✅ Initialized inventory for {character_name} (STR {strength_score}, capacity {carrying_capacity} lbs)")
            
            return {
                "success": True,
                "message": f"Inventory initialized for {character_name}",
                "carrying_capacity": carrying_capacity
            }
            
        except Exception as e:
            return {"success": False, "error": f"Failed to initialize inventory: {str(e)}"}
    
    def _handle_add_item(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Add item to character inventory"""
        try:
            character_name = message_data.get("character", "").strip().lower()
            # Support both 'item' and 'item_name' for compatibility
            item_name = message_data.get("item", message_data.get("item_name", "")).strip().lower()
            quantity = message_data.get("quantity", 1)
            
            if not character_name or not item_name:
                return {"success": False, "error": "Character name and item name are required"}
            
            # Check if character inventory exists (don't auto-create for unknown characters)
            if character_name not in self.character_inventories:
                return {"success": False, "error": f"Character '{character_name}' not found. Initialize inventory first."}
            
            inventory = self.character_inventories[character_name]
            
            # Get item info
            item_info = self._get_item_data(item_name)
            if not item_info:
                return {"success": False, "error": f"Unknown item: {item_name}"}
            
            # Add to inventory
            if item_name in inventory["items"]:
                inventory["items"][item_name]["quantity"] += quantity
            else:
                inventory["items"][item_name] = {
                    "name": item_info["name"],
                    "type": item_info["type"],
                    "weight": item_info.get("weight", 0),
                    "value": item_info.get("value", 0),
                    "quantity": quantity,
                    "properties": item_info.get("properties", []),
                    "description": item_info.get("description", "")
                }
            
            # Update total weight
            self._recalculate_inventory_weight(character_name)
            
            if self.verbose:
                print(f"✅ Added {quantity}x {item_name} to {character_name}'s inventory")
            
            return {
                "success": True,
                "message": f"Added {quantity}x {item_name} to inventory",
                "inventory": inventory
            }
            
        except Exception as e:
            return {"success": False, "error": f"Failed to add item: {str(e)}"}
    
    def _handle_remove_item(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Remove item from character inventory"""
        try:
            character_name = message_data.get("character", "").strip().lower()
            item_name = message_data.get("item", "").strip().lower()
            quantity = message_data.get("quantity", 1)
            
            if not character_name or not item_name:
                return {"success": False, "error": "Character name and item name are required"}
            
            if character_name not in self.character_inventories:
                return {"success": False, "error": f"No inventory found for {character_name}"}
            
            inventory = self.character_inventories[character_name]
            
            if item_name not in inventory["items"]:
                return {"success": False, "error": f"Item {item_name} not found in inventory"}
            
            # Remove quantity
            current_quantity = inventory["items"][item_name]["quantity"]
            if quantity >= current_quantity:
                # Remove item completely
                del inventory["items"][item_name]
                quantity_removed = current_quantity
            else:
                # Reduce quantity
                inventory["items"][item_name]["quantity"] -= quantity
                quantity_removed = quantity
            
            # Update total weight
            self._recalculate_inventory_weight(character_name)
            
            if self.verbose:
                print(f"✅ Removed {quantity_removed}x {item_name} from {character_name}'s inventory")
            
            return {
                "success": True,
                "message": f"Removed {quantity_removed}x {item_name} from inventory",
                "inventory": inventory
            }
            
        except Exception as e:
            return {"success": False, "error": f"Failed to remove item: {str(e)}"}
    
    def _handle_get_inventory(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get character's complete inventory"""
        try:
            character_name = message_data.get("character", "").strip().lower()
            
            if not character_name:
                return {"success": False, "error": "Character name is required"}
            
            if character_name not in self.character_inventories:
                # Return empty inventory
                return {
                    "success": True,
                    "inventory": {
                        "items": {},
                        "equipped": {},
                        "total_weight": 0.0,
                        "carrying_capacity": 150
                    }
                }
            
            inventory = self.character_inventories[character_name]
            
            return {"success": True, "inventory": inventory}
            
        except Exception as e:
            return {"success": False, "error": f"Failed to get inventory: {str(e)}"}
    
    def _handle_equip_item(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Equip an item from inventory"""
        try:
            character_name = message_data.get("character", "").strip().lower()
            item_name = message_data.get("item", "").strip().lower()
            slot = message_data.get("slot", "").lower()
            
            if not character_name or not item_name:
                return {"success": False, "error": "Character name and item name are required"}
            
            if character_name not in self.character_inventories:
                return {"success": False, "error": f"No inventory found for {character_name}"}
            
            inventory = self.character_inventories[character_name]
            
            if item_name not in inventory["items"]:
                return {"success": False, "error": f"Item {item_name} not found in inventory"}
            
            item = inventory["items"][item_name]
            item_data = self._get_item_data(item_name)
            
            # Determine equipment slot if not specified
            if not slot:
                slot = self._determine_equipment_slot(item_data)
            
            if not slot:
                return {"success": False, "error": f"Cannot determine equipment slot for {item_name}"}
            
            # Check if slot is already occupied
            if slot in inventory["equipped"]:
                return {
                    "success": False, 
                    "error": f"Slot {slot} is already occupied by {inventory['equipped'][slot]['name']}"
                }
            
            # Equip the item
            inventory["equipped"][slot] = {
                "name": item["name"],
                "type": item["type"],
                "properties": item.get("properties", []),
                "bonuses": item_data.get("bonuses", {}),
                "ac_bonus": item_data.get("ac_bonus", 0),
                "damage": item_data.get("damage", ""),
                "damage_type": item_data.get("damage_type", "")
            }
            
            # Remove one from inventory (if stackable)
            if item["quantity"] > 1:
                inventory["items"][item_name]["quantity"] -= 1
            else:
                del inventory["items"][item_name]
            
            if self.verbose:
                print(f"✅ {character_name} equipped {item_name} in {slot} slot")
            
            return {
                "success": True,
                "message": f"Equipped {item_name} in {slot} slot",
                "equipped_item": inventory["equipped"][slot],
                "inventory": inventory
            }
            
        except Exception as e:
            return {"success": False, "error": f"Failed to equip item: {str(e)}"}
    
    def _handle_unequip_item(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Unequip an item to inventory"""
        try:
            character_name = message_data.get("character", "").strip().lower()
            slot = message_data.get("slot", "").lower()
            
            if not character_name or not slot:
                return {"success": False, "error": "Character name and equipment slot are required"}
            
            if character_name not in self.character_inventories:
                return {"success": False, "error": f"No inventory found for {character_name}"}
            
            inventory = self.character_inventories[character_name]
            
            if slot not in inventory["equipped"]:
                return {"success": False, "error": f"No item equipped in {slot} slot"}
            
            equipped_item = inventory["equipped"][slot]
            item_name = equipped_item["name"].lower()
            
            # Move back to inventory
            if item_name in inventory["items"]:
                inventory["items"][item_name]["quantity"] += 1
            else:
                # Recreate item in inventory
                item_data = self._get_item_data(item_name)
                inventory["items"][item_name] = {
                    "name": equipped_item["name"],
                    "type": equipped_item["type"],
                    "weight": item_data.get("weight", 0),
                    "value": item_data.get("value", 0),
                    "quantity": 1,
                    "properties": equipped_item.get("properties", []),
                    "description": item_data.get("description", "")
                }
            
            # Remove from equipped
            del inventory["equipped"][slot]
            
            # Update total weight
            self._recalculate_inventory_weight(character_name)
            
            if self.verbose:
                print(f"✅ {character_name} unequipped {equipped_item['name']} from {slot} slot")
            
            return {
                "success": True,
                "message": f"Unequipped {equipped_item['name']} from {slot} slot",
                "inventory": inventory
            }
            
        except Exception as e:
            return {"success": False, "error": f"Failed to unequip item: {str(e)}"}
    
    def _handle_get_equipped_items(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get all equipped items for a character"""
        try:
            character_name = message_data.get("character", "").strip().lower()
            
            if not character_name:
                return {"success": False, "error": "Character name is required"}
            
            if character_name not in self.character_inventories:
                return {"success": True, "equipped": {}}
            
            equipped = self.character_inventories[character_name]["equipped"]
            return {"success": True, "equipped": equipped}
            
        except Exception as e:
            return {"success": False, "error": f"Failed to get equipped items: {str(e)}"}
    
    def _handle_search_items(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Search for items in the database"""
        try:
            query = message_data.get("query", "").lower()
            item_type = message_data.get("type", "").lower()
            
            if not query and not item_type:
                return {"success": False, "error": "Search query or item type is required"}
            
            results = []
            for item_name, item_data in self.item_database.items():
                if query and query in item_name.lower():
                    results.append(item_data)
                elif item_type and item_data.get("type", "").lower() == item_type:
                    results.append(item_data)
            
            return {"success": True, "results": results, "count": len(results)}
            
        except Exception as e:
            return {"success": False, "error": f"Failed to search items: {str(e)}"}
    
    def _handle_get_item_info(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get detailed information about an item"""
        try:
            item_name = message_data.get("item", "").strip().lower()
            
            if not item_name:
                return {"success": False, "error": "Item name is required"}
            
            item_data = self._get_item_data(item_name)
            if not item_data:
                return {"success": False, "error": f"Item '{item_name}' not found"}
            
            return {"success": True, "item": item_data}
            
        except Exception as e:
            return {"success": False, "error": f"Failed to get item info: {str(e)}"}
    
    def _handle_transfer_item(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Transfer item between characters"""
        try:
            from_character = message_data.get("from", "").strip().lower()
            to_character = message_data.get("to", "").strip().lower()
            item_name = message_data.get("item", "").strip().lower()
            quantity = message_data.get("quantity", 1)
            
            if not from_character or not to_character or not item_name:
                return {"success": False, "error": "From character, to character, and item name are required"}
            
            # Remove from source
            remove_result = self._handle_remove_item({
                "character": from_character,
                "item": item_name,
                "quantity": quantity
            })
            
            if not remove_result["success"]:
                return remove_result
            
            # Add to destination
            add_result = self._handle_add_item({
                "character": to_character,
                "item": item_name,
                "quantity": quantity
            })
            
            if not add_result["success"]:
                # If add fails, restore to original character
                self._handle_add_item({
                    "character": from_character,
                    "item": item_name,
                    "quantity": quantity
                })
                return add_result
            
            return {
                "success": True,
                "message": f"Transferred {quantity}x {item_name} from {from_character} to {to_character}"
            }
            
        except Exception as e:
            return {"success": False, "error": f"Failed to transfer item: {str(e)}"}
    
    def _handle_calculate_carrying_capacity(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate carrying capacity based on strength"""
        try:
            strength_score = message_data.get("strength", 10)
            
            # D&D 5e carrying capacity = STR score × 15 pounds
            carrying_capacity = strength_score * 15
            
            # Encumbrance thresholds
            encumbrance_thresholds = {
                "unencumbered": carrying_capacity // 3,
                "encumbered": (carrying_capacity * 2) // 3,
                "heavily_encumbered": carrying_capacity
            }
            
            return {
                "success": True,
                "carrying_capacity": carrying_capacity,
                "encumbrance_thresholds": encumbrance_thresholds
            }
            
        except Exception as e:
            return {"success": False, "error": f"Failed to calculate carrying capacity: {str(e)}"}
    
    def _handle_get_armor_class(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate AC from equipped armor and items"""
        try:
            character_name = message_data.get("character", "").strip().lower()
            base_dex_modifier = message_data.get("dex_modifier", 0)
            
            if character_name not in self.character_inventories:
                return {"success": True, "armor_class": 10 + base_dex_modifier, "breakdown": {"base": 10, "dex": base_dex_modifier}}
            
            equipped = self.character_inventories[character_name]["equipped"]
            
            base_ac = 10
            ac_bonus = 0
            dex_modifier = base_dex_modifier
            max_dex_bonus = None
            
            # Check for armor
            if "armor" in equipped:
                armor = equipped["armor"]
                armor_data = self._get_item_data(armor["name"].lower())
                
                if armor_data:
                    base_ac = armor_data.get("base_ac", 10)
                    max_dex_bonus = armor_data.get("max_dex_bonus", None)
                    ac_bonus += armor_data.get("ac_bonus", 0)
            
            # Apply dex modifier with max limit
            if max_dex_bonus is not None:
                dex_modifier = min(dex_modifier, max_dex_bonus)
            
            # Check for shield
            if "shield" in equipped:
                shield_data = self._get_item_data(equipped["shield"]["name"].lower())
                if shield_data:
                    ac_bonus += shield_data.get("ac_bonus", 2)
            
            # Check for other AC bonuses
            for slot, item in equipped.items():
                if slot not in ["armor", "shield"]:
                    ac_bonus += item.get("ac_bonus", 0)
            
            total_ac = base_ac + dex_modifier + ac_bonus
            
            breakdown = {
                "base": base_ac,
                "dex": dex_modifier,
                "armor_bonus": ac_bonus
            }
            
            return {
                "success": True,
                "armor_class": total_ac,
                "breakdown": breakdown
            }
            
        except Exception as e:
            return {"success": False, "error": f"Failed to calculate AC: {str(e)}"}
    
    def _handle_create_custom_item(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a custom item and add to database"""
        try:
            item_data = message_data.get("item_data", {})
            
            required_fields = ["name", "type"]
            for field in required_fields:
                if field not in item_data:
                    return {"success": False, "error": f"Required field missing: {field}"}
            
            item_name = item_data["name"].lower()
            
            # Add to item database
            self.item_database[item_name] = item_data
            
            # Save to file
            custom_items_file = os.path.join(self.items_dir, "custom_items.json")
            try:
                if os.path.exists(custom_items_file):
                    with open(custom_items_file, 'r') as f:
                        custom_items = json.load(f)
                else:
                    custom_items = {}
                
                custom_items[item_name] = item_data
                
                with open(custom_items_file, 'w') as f:
                    json.dump(custom_items, f, indent=2)
            except Exception as e:
                if self.verbose:
                    print(f"⚠️ Failed to save custom item to file: {e}")
            
            return {
                "success": True,
                "message": f"Created custom item: {item_data['name']}",
                "item": item_data
            }
            
        except Exception as e:
            return {"success": False, "error": f"Failed to create custom item: {str(e)}"}
    
    def _handle_get_carrying_capacity(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get carrying capacity status for a character"""
        try:
            character_name = message_data.get("character", "").strip().lower()
            
            if not character_name:
                return {"success": False, "error": "Character name is required"}
            
            if character_name not in self.character_inventories:
                return {"success": False, "error": f"No inventory found for {character_name}"}
            
            inventory = self.character_inventories[character_name]
            carrying_capacity = inventory.get("carrying_capacity", 150)
            total_weight = inventory.get("total_weight", 0.0)
            
            # Calculate encumbrance levels
            unencumbered_limit = carrying_capacity // 3
            encumbered_limit = (carrying_capacity * 2) // 3
            
            encumbrance_status = "unencumbered"
            if total_weight > encumbered_limit:
                encumbrance_status = "heavily_encumbered"
            elif total_weight > unencumbered_limit:
                encumbrance_status = "encumbered"
            
            return {
                "success": True,
                "character": character_name,
                "carrying_capacity": carrying_capacity,
                "total_weight": total_weight,
                "encumbrance_status": encumbrance_status,
                "weight_limits": {
                    "unencumbered": unencumbered_limit,
                    "encumbered": encumbered_limit,
                    "maximum": carrying_capacity
                }
            }
            
        except Exception as e:
            return {"success": False, "error": f"Failed to get carrying capacity: {str(e)}"}
    
    # Helper methods
    def _load_item_database(self):
        """Load item database from files"""
        self.item_database = {}
        
        # Load custom items if they exist
        custom_items_file = os.path.join(self.items_dir, "custom_items.json")
        if os.path.exists(custom_items_file):
            try:
                with open(custom_items_file, 'r') as f:
                    custom_items = json.load(f)
                self.item_database.update(custom_items)
            except Exception as e:
                if self.verbose:
                    print(f"⚠️ Failed to load custom items: {e}")
    
    def _add_basic_items(self):
        """Add basic D&D items to the database"""
        basic_items = {
            # Weapons
            "longsword": {
                "name": "Longsword",
                "type": "weapon",
                "weapon_type": "martial melee",
                "damage": "1d8",
                "damage_type": "slashing",
                "weight": 3,
                "value": 15,
                "properties": ["versatile (1d10)"],
                "description": "A standard longsword"
            },
            "shortsword": {
                "name": "Shortsword",
                "type": "weapon",
                "weapon_type": "martial melee",
                "damage": "1d6",
                "damage_type": "piercing",
                "weight": 2,
                "value": 10,
                "properties": ["finesse", "light"],
                "description": "A short, light sword"
            },
            "great sword": {
                "name": "Great Sword",
                "type": "weapon",
                "weapon_type": "martial melee",
                "damage": "2d6",
                "damage_type": "slashing",
                "weight": 6,
                "value": 50,
                "properties": ["heavy", "two-handed"],
                "description": "A large two-handed sword"
            },
            "bow": {
                "name": "Shortbow",
                "type": "weapon",
                "weapon_type": "simple ranged",
                "damage": "1d6",
                "damage_type": "piercing",
                "weight": 2,
                "value": 25,
                "properties": ["ammunition", "range (80/320)", "two-handed"],
                "description": "A simple shortbow"
            },
            
            # Armor
            "leather armor": {
                "name": "Leather Armor",
                "type": "armor",
                "armor_type": "light",
                "base_ac": 11,
                "max_dex_bonus": None,
                "weight": 10,
                "value": 10,
                "description": "Basic leather armor"
            },
            "chain mail": {
                "name": "Chain Mail",
                "type": "armor",
                "armor_type": "heavy",
                "base_ac": 16,
                "max_dex_bonus": 0,
                "weight": 55,
                "value": 75,
                "description": "Heavy chain mail armor"
            },
            "plate armor": {
                "name": "Plate Armor",
                "type": "armor",
                "armor_type": "heavy",
                "base_ac": 18,
                "max_dex_bonus": 0,
                "weight": 65,
                "value": 1500,
                "description": "Heavy plate armor providing excellent protection"
            },
            "shield": {
                "name": "Shield",
                "type": "shield",
                "ac_bonus": 2,
                "weight": 6,
                "value": 10,
                "description": "A standard shield"
            },
            
            # Equipment
            "rope": {
                "name": "Rope",
                "type": "adventuring gear",
                "weight": 10,
                "value": 2,
                "description": "Hemp rope, 50 feet"
            },
            "backpack": {
                "name": "Backpack",
                "type": "adventuring gear",
                "weight": 5,
                "value": 2,
                "description": "A leather backpack"
            },
            "torch": {
                "name": "Torch",
                "type": "adventuring gear",
                "weight": 1,
                "value": 0.01,
                "description": "A torch that burns for 1 hour"
            },
            "potion of healing": {
                "name": "Potion of Healing",
                "type": "potion",
                "weight": 0.5,
                "value": 50,
                "healing": "2d4+2",
                "description": "Heals 2d4+2 hit points when consumed"
            }
        }
        
        # Add to main database
        self.item_database.update(basic_items)
    
    def _get_item_data(self, item_name: str) -> Optional[Dict[str, Any]]:
        """Get item data from database with case-insensitive lookup"""
        item_name_lower = item_name.lower()
        
        # First try exact match
        if item_name_lower in self.item_database:
            return self.item_database[item_name_lower]
        
        # Try partial matching for common variations
        for db_item_name, item_data in self.item_database.items():
            if item_name_lower in db_item_name or db_item_name in item_name_lower:
                return item_data
        
        return None
    
    def _determine_equipment_slot(self, item_data: Dict[str, Any]) -> Optional[str]:
        """Determine appropriate equipment slot for an item"""
        item_type = item_data.get("type", "").lower()
        
        if item_type == "weapon":
            return "main_hand"  # Could be expanded for two-handed, off-hand, etc.
        elif item_type == "armor":
            return "armor"
        elif item_type == "shield":
            return "shield"
        elif item_type == "ring":
            return "ring"  # Could be ring1, ring2
        elif item_type == "amulet" or item_type == "necklace":
            return "neck"
        elif item_type == "cloak":
            return "cloak"
        elif item_type == "boots":
            return "feet"
        elif item_type == "gloves":
            return "hands"
        elif item_type == "helmet":
            return "head"
        
        return None
    
    def _recalculate_inventory_weight(self, character_name: str):
        """Recalculate total inventory weight for a character"""
        if character_name not in self.character_inventories:
            return
        
        inventory = self.character_inventories[character_name]
        total_weight = 0.0
        
        # Calculate weight from items
        for item_name, item in inventory["items"].items():
            item_weight = item.get("weight", 0)
            quantity = item.get("quantity", 1)
            total_weight += item_weight * quantity
        
        # Calculate weight from equipped items
        for slot, item in inventory["equipped"].items():
            item_data = self._get_item_data(item["name"].lower())
            if item_data:
               total_weight += item_data.get("weight", 0)
       
        inventory["total_weight"] = total_weight
   
    def _handle_game_state_updated(self, message):
       """Handle game_state_updated event - no action needed for inventory manager"""
       # Inventory manager doesn't need to respond to game state updates
       # This handler exists only to prevent "no handler" error messages
       pass