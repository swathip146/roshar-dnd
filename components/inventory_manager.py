"""
Inventory Manager - Item tracking and loot distribution
Following Haystack component patterns for D&D inventory management
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum
from haystack import component


class ItemType(Enum):
    """D&D item categories"""
    WEAPON = "weapon"
    ARMOR = "armor"
    SHIELD = "shield"
    CONSUMABLE = "consumable"
    TOOL = "tool"
    TREASURE = "treasure"
    MAGIC_ITEM = "magic_item"
    AMMUNITION = "ammunition"
    GEAR = "gear"
    CONTAINER = "container"


class ItemRarity(Enum):
    """D&D item rarity levels"""
    COMMON = "common"
    UNCOMMON = "uncommon"
    RARE = "rare"
    VERY_RARE = "very_rare"
    LEGENDARY = "legendary"
    ARTIFACT = "artifact"


@dataclass
class Item:
    """Complete D&D item with metadata"""
    id: str
    name: str
    item_type: ItemType
    rarity: ItemRarity
    weight: float  # in pounds
    value: int  # in gold pieces
    description: str
    properties: Dict[str, Any]
    magical: bool = False
    cursed: bool = False
    attunement_required: bool = False
    charges: Optional[int] = None
    max_charges: Optional[int] = None


@dataclass
class InventorySlot:
    """Individual inventory slot with item and quantity"""
    item: Item
    quantity: int
    equipped: bool = False
    attuned: bool = False


@component
class InventoryManager:
    """
    Manages character inventories and loot distribution following Haystack patterns
    Handles D&D-specific inventory mechanics like encumbrance, attunement, etc.
    """
    
    def __init__(self):
        self.character_inventories: Dict[str, List[InventorySlot]] = {}
        self.item_database: Dict[str, Item] = {}
        self.loot_tables: Dict[str, List[Dict[str, Any]]] = {}
        
        # Initialize with basic D&D items
        self._initialize_basic_items()
        
        print("🎒 Inventory Manager initialized")
    
    def _initialize_basic_items(self):
        """Initialize database with basic D&D items"""
        
        basic_items = [
            Item(
                id="shortsword",
                name="Shortsword",
                item_type=ItemType.WEAPON,
                rarity=ItemRarity.COMMON,
                weight=2.0,
                value=10,
                description="A light, versatile blade",
                properties={"damage": "1d6", "damage_type": "piercing", "finesse": True, "light": True}
            ),
            Item(
                id="leather_armor",
                name="Leather Armor",
                item_type=ItemType.ARMOR,
                rarity=ItemRarity.COMMON,
                weight=10.0,
                value=5,
                description="Basic leather protection",
                properties={"ac": 11, "max_dex_bonus": None, "stealth_disadvantage": False}
            ),
            Item(
                id="healing_potion",
                name="Potion of Healing",
                item_type=ItemType.CONSUMABLE,
                rarity=ItemRarity.COMMON,
                weight=0.5,
                value=50,
                description="A swirling red liquid that restores health",
                properties={"healing": "2d4+2", "action": "consume"}
            ),
            Item(
                id="rope",
                name="Hemp Rope (50 feet)",
                item_type=ItemType.GEAR,
                rarity=ItemRarity.COMMON,
                weight=10.0,
                value=2,
                description="Strong hemp rope for climbing and binding",
                properties={"length": 50, "material": "hemp"}
            ),
            Item(
                id="gold_piece",
                name="Gold Piece",
                item_type=ItemType.TREASURE,
                rarity=ItemRarity.COMMON,
                weight=0.02,
                value=1,
                description="Standard currency of the realm",
                properties={"currency": True}
            )
        ]
        
        for item in basic_items:
            self.item_database[item.id] = item
    
    @component.output_types(success=bool, result=dict, message=str)
    def run(self, operation: str, **kwargs) -> Dict[str, Any]:
        """Main Haystack component interface for inventory operations"""
        
        if operation == "add_item":
            return self.add_item_to_character(
                kwargs.get("character_id", "player"),
                kwargs.get("item_id", ""),
                kwargs.get("quantity", 1)
            )
        elif operation == "remove_item":
            return self.remove_item_from_character(
                kwargs.get("character_id", "player"),
                kwargs.get("item_id", ""),
                kwargs.get("quantity", 1)
            )
        elif operation == "equip_item":
            return self.equip_item(
                kwargs.get("character_id", "player"),
                kwargs.get("item_id", "")
            )
        elif operation == "check_encumbrance":
            return {
                "success": True,
                "result": self.check_encumbrance(
                    kwargs.get("character_id", "player"),
                    kwargs.get("strength_score", 10)
                ),
                "message": "Encumbrance checked"
            }
        elif operation == "generate_loot":
            return {
                "success": True,
                "result": self.generate_loot(
                    kwargs.get("loot_table", "goblin"),
                    kwargs.get("character_level", 1)
                ),
                "message": "Loot generated"
            }
        elif operation == "inventory_summary":
            return {
                "success": True,
                "result": self.get_inventory_summary(kwargs.get("character_id", "player")),
                "message": "Inventory summary retrieved"
            }
        else:
            return {"success": False, "result": {}, "message": f"Unknown operation: {operation}"}
    
    def add_item_to_character(self, character_id: str, item_id: str, quantity: int = 1) -> Dict[str, Any]:
        """Add item to character inventory"""
        
        if character_id not in self.character_inventories:
            self.character_inventories[character_id] = []
        
        if item_id not in self.item_database:
            return {
                "success": False,
                "inventory": {},
                "message": f"Item '{item_id}' not found in database"
            }
        
        item = self.item_database[item_id]
        inventory = self.character_inventories[character_id]
        
        # Check for existing slot with same item
        existing_slot = None
        for slot in inventory:
            if slot.item.id == item_id:
                existing_slot = slot
                break
        
        if existing_slot:
            # Stack with existing item
            existing_slot.quantity += quantity
        else:
            # Create new inventory slot
            new_slot = InventorySlot(
                item=item,
                quantity=quantity,
                equipped=False,
                attuned=False
            )
            inventory.append(new_slot)
        
        # Check encumbrance
        encumbrance_result = self._check_encumbrance(character_id)
        
        return {
            "success": True,
            "result": self._format_inventory(character_id),
            "message": f"Added {quantity}x {item.name} to {character_id}'s inventory",
            "encumbrance": encumbrance_result
        }
    
    def remove_item_from_character(self, character_id: str, item_id: str, quantity: int = 1) -> Dict[str, Any]:
        """Remove item from character inventory"""
        
        if character_id not in self.character_inventories:
            return {
                "success": False,
                "result": {},
                "message": f"No inventory found for {character_id}"
            }
        
        inventory = self.character_inventories[character_id]
        
        # Find the item slot
        target_slot = None
        for slot in inventory:
            if slot.item.id == item_id:
                target_slot = slot
                break
        
        if not target_slot:
            return {
                "success": False,
                "result": self._format_inventory(character_id),
                "message": f"Item '{item_id}' not found in inventory"
            }
        
        if target_slot.quantity < quantity:
            return {
                "success": False,
                "result": self._format_inventory(character_id),
                "message": f"Not enough {target_slot.item.name} (has {target_slot.quantity}, requested {quantity})"
            }
        
        # Remove quantity
        target_slot.quantity -= quantity
        
        # Remove slot if quantity reaches zero
        if target_slot.quantity <= 0:
            inventory.remove(target_slot)
        
        return {
            "success": True,
            "result": self._format_inventory(character_id),
            "message": f"Removed {quantity}x {target_slot.item.name} from inventory"
        }
    
    def equip_item(self, character_id: str, item_id: str) -> Dict[str, Any]:
        """Equip an item from inventory"""
        
        if character_id not in self.character_inventories:
            return {
                "success": False,
                "result": {},
                "message": f"No inventory found for {character_id}"
            }
        
        inventory = self.character_inventories[character_id]
        
        # Find the item slot
        target_slot = None
        for slot in inventory:
            if slot.item.id == item_id and slot.quantity > 0:
                target_slot = slot
                break
        
        if not target_slot:
            return {
                "success": False,
                "result": {},
                "message": f"Item '{item_id}' not available for equipping"
            }
        
        # Check if item can be equipped
        if target_slot.item.item_type not in [ItemType.WEAPON, ItemType.ARMOR, ItemType.SHIELD]:
            return {
                "success": False,
                "result": {},
                "message": f"{target_slot.item.name} cannot be equipped"
            }
        
        # Check for conflicts (simplified - would be more complex in full D&D)
        equipped_items = [slot for slot in inventory if slot.equipped]
        conflict_check = self._check_equipment_conflicts(target_slot.item, equipped_items)
        
        if not conflict_check["can_equip"]:
            return {
                "success": False,
                "result": {},
                "message": conflict_check["reason"]
            }
        
        # Equip the item
        target_slot.equipped = True
        
        # Handle attunement for magic items
        attunement_result = {}
        if target_slot.item.attunement_required:
            attunement_result = self._handle_attunement(character_id, target_slot)
        
        return {
            "success": True,
            "result": self._get_equipped_items(character_id),
            "message": f"Equipped {target_slot.item.name}",
            "attunement": attunement_result
        }
    
    def _check_equipment_conflicts(self, new_item: Item, equipped_items: List[InventorySlot]) -> Dict[str, Any]:
        """Check for equipment conflicts (simplified)"""
        
        # Basic conflict checking - would be more sophisticated in full implementation
        if new_item.item_type == ItemType.ARMOR:
            for slot in equipped_items:
                if slot.item.item_type == ItemType.ARMOR:
                    return {
                        "can_equip": False,
                        "reason": f"Already wearing {slot.item.name}. Remove it first."
                    }
        
        return {"can_equip": True, "reason": ""}
    
    def _handle_attunement(self, character_id: str, item_slot: InventorySlot) -> Dict[str, Any]:
        """Handle magic item attunement"""
        
        if not item_slot.item.attunement_required:
            return {"attunement_needed": False}
        
        # Check current attunement count (max 3 in D&D)
        inventory = self.character_inventories[character_id]
        attuned_count = sum(1 for slot in inventory if slot.attuned)
        
        if attuned_count >= 3:
            return {
                "attunement_needed": True,
                "attuned": False,
                "reason": "Maximum attunement slots (3) already used",
                "current_attuned": attuned_count
            }
        
        # Attune the item
        item_slot.attuned = True
        
        return {
            "attunement_needed": True,
            "attuned": True,
            "reason": f"Successfully attuned to {item_slot.item.name}",
            "current_attuned": attuned_count + 1
        }
    
    def check_encumbrance(self, character_id: str, strength_score: int = 10) -> Dict[str, Any]:
        """Check character encumbrance based on D&D rules"""
        
        if character_id not in self.character_inventories:
            return {
                "total_weight": 0.0,
                "carrying_capacity": strength_score * 15,
                "encumbered": False
            }
        
        inventory = self.character_inventories[character_id]
        total_weight = 0.0
        
        for slot in inventory:
            total_weight += slot.item.weight * slot.quantity
        
        # D&D 5e encumbrance rules
        carrying_capacity = strength_score * 15  # pounds
        heavily_encumbered_threshold = carrying_capacity * 2/3
        encumbered_threshold = carrying_capacity * 1/3
        
        encumbrance_level = "normal"
        if total_weight > carrying_capacity:
            encumbrance_level = "overloaded"
        elif total_weight > heavily_encumbered_threshold:
            encumbrance_level = "heavily_encumbered"
        elif total_weight > encumbered_threshold:
            encumbrance_level = "encumbered"
        
        return {
            "total_weight": total_weight,
            "carrying_capacity": carrying_capacity,
            "encumbered": encumbrance_level != "normal",
            "encumbrance_level": encumbrance_level,
            "weight_breakdown": {
                "current": total_weight,
                "encumbered_at": encumbered_threshold,
                "heavily_encumbered_at": heavily_encumbered_threshold,
                "max_capacity": carrying_capacity
            }
        }
    
    def _check_encumbrance(self, character_id: str) -> Dict[str, Any]:
        """Internal encumbrance check with default strength"""
        return self.check_encumbrance(character_id, 10)
    
    def _format_inventory(self, character_id: str) -> Dict[str, Any]:
        """Format inventory for display"""
        
        if character_id not in self.character_inventories:
            return {
                "character_id": character_id,
                "items": [],
                "total_items": 0,
                "total_weight": 0.0,
                "total_value": 0
            }
        
        inventory = self.character_inventories[character_id]
        formatted_items = []
        total_weight = 0.0
        total_value = 0
        
        for slot in inventory:
            item_data = {
                "id": slot.item.id,
                "name": slot.item.name,
                "type": slot.item.item_type.value,
                "rarity": slot.item.rarity.value,
                "quantity": slot.quantity,
                "weight": slot.item.weight,
                "value": slot.item.value,
                "equipped": slot.equipped,
                "attuned": slot.attuned,
                "magical": slot.item.magical,
                "description": slot.item.description
            }
            
            formatted_items.append(item_data)
            total_weight += slot.item.weight * slot.quantity
            total_value += slot.item.value * slot.quantity
        
        return {
            "character_id": character_id,
            "items": formatted_items,
            "total_items": len(formatted_items),
            "total_weight": total_weight,
            "total_value": total_value,
            "equipped_items": len([item for item in formatted_items if item["equipped"]]),
            "attuned_items": len([item for item in formatted_items if item["attuned"]])
        }
    
    def _get_equipped_items(self, character_id: str) -> Dict[str, Any]:
        """Get only equipped items"""
        
        if character_id not in self.character_inventories:
            return {"equipped_items": []}
        
        inventory = self.character_inventories[character_id]
        equipped = []
        
        for slot in inventory:
            if slot.equipped:
                equipped.append({
                    "id": slot.item.id,
                    "name": slot.item.name,
                    "type": slot.item.item_type.value,
                    "attuned": slot.attuned,
                    "properties": slot.item.properties
                })
        
        return {"equipped_items": equipped}
    
    def generate_loot(self, loot_table: str, character_level: int = 1) -> Dict[str, Any]:
        """Generate random loot based on loot table and character level"""
        
        import random
        
        # Basic loot generation (would be more sophisticated in full implementation)
        loot_items = []
        
        if loot_table == "goblin":
            # Simple goblin loot
            if random.random() < 0.3:  # 30% chance
                gold_amount = random.randint(1, 6)
                loot_items.append({"item_id": "gold_piece", "quantity": gold_amount})
            
            if random.random() < 0.1:  # 10% chance
                loot_items.append({"item_id": "shortsword", "quantity": 1})
                
        elif loot_table == "treasure_chest":
            # Treasure chest loot
            gold_amount = random.randint(10, 100)
            loot_items.append({"item_id": "gold_piece", "quantity": gold_amount})
            
            if random.random() < 0.5:  # 50% chance
                loot_items.append({"item_id": "healing_potion", "quantity": 1})
        
        return {
            "loot": {
                "table": loot_table,
                "character_level": character_level,
                "items": loot_items
            }
        }
    
    def get_inventory_summary(self, character_id: str) -> Dict[str, Any]:
        """Get comprehensive inventory summary"""
        
        inventory_data = self._format_inventory(character_id)
        equipped_data = self._get_equipped_items(character_id)
        encumbrance_data = self._check_encumbrance(character_id)
        
        return {
            "inventory": inventory_data,
            "equipped": equipped_data,
            "encumbrance": encumbrance_data,
            "summary": {
                "has_items": inventory_data["total_items"] > 0,
                "can_carry_more": not encumbrance_data["encumbered"],
                "has_magic_items": any(item["magical"] for item in inventory_data["items"]),
                "currency_value": sum(item["value"] * item["quantity"] 
                                    for item in inventory_data["items"] 
                                    if item["type"] == "treasure")
            }
        }


# Factory function for easy integration
def create_inventory_manager() -> InventoryManager:
    """Factory function to create configured inventory manager"""
    return InventoryManager()


# Integration helper for orchestrator
def integrate_inventory_manager_with_orchestrator(orchestrator, inventory_manager: InventoryManager):
    """Helper function to integrate inventory manager with orchestrator"""
    
    def handle_add_item(request: Dict[str, Any]) -> Dict[str, Any]:
        character_id = request.get("character_id", "player")
        item_id = request.get("item_id")
        quantity = request.get("quantity", 1)
        
        result = inventory_manager.add_item_to_character(character_id, item_id, quantity)
        return {"success": result["success"], "data": result}
    
    def handle_inventory_summary(request: Dict[str, Any]) -> Dict[str, Any]:
        character_id = request.get("character_id", "player")
        result = inventory_manager.get_inventory_summary(character_id)
        return {"success": True, "data": result}
    
    # Register handlers with orchestrator
    orchestrator.register_handler("add_item", handle_add_item)
    orchestrator.register_handler("inventory_summary", handle_inventory_summary)
    orchestrator.register_handler("check_encumbrance", 
                                 lambda req: {"success": True, "data": inventory_manager.check_encumbrance(
                                     req.get("character_id", "player"), req.get("strength", 10))})
    
    print("🔗 Inventory Manager integrated with orchestrator")


# Example usage and testing
if __name__ == "__main__":
    # Test inventory manager functionality
    manager = create_inventory_manager()
    
    print("=== Inventory Manager Test ===")
    
    # Add some items
    result1 = manager.add_item_to_character("player", "shortsword", 1)
    print(f"Add shortsword: {result1['success']} - {result1['message']}")
    
    result2 = manager.add_item_to_character("player", "healing_potion", 3)
    print(f"Add potions: {result2['success']} - {result2['message']}")
    
    result3 = manager.add_item_to_character("player", "gold_piece", 50)
    print(f"Add gold: {result3['success']} - {result3['message']}")
    
    # Check inventory
    summary = manager.get_inventory_summary("player")
    print(f"Inventory summary: {summary['inventory']['total_items']} items, {summary['inventory']['total_value']} gp value")
    
    # Test equipment
    equip_result = manager.equip_item("player", "shortsword")
    print(f"Equip sword: {equip_result['success']} - {equip_result['message']}")
    
    # Test loot generation
    loot = manager.generate_loot("goblin", 1)
    print(f"Goblin loot: {loot['loot']['items']}")