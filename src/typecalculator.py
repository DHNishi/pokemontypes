'''
Created on Feb 21, 2014

@author: daniel
'''

from smogonreader import SmogonReader
from utils import memoized
import sqlite3
import itertools
import optparse

class Type(object):
    def __init__(self, newType, se, neutral, resist, immune, value):
        self.myTypes = newType
        self.se = se
        self.neutral = neutral
        self.resist = resist
        self.immune = immune
        self.value = value
        
    def toString(self):
        printableTypes = [str(types[1]) for types in self.myTypes]
        newString = str(printableTypes) + " " + str(len(self.se)) + " " + str(len(self.resist)) + " " + str(len(self.immune)) + " " + str(self.value)
        return newString

class TypeCombination():
    def __init__(self, firstType, secondType, se, resist, immune):
        self.firstType = firstType
        self.secondType = secondType
        self.se = se
        self.resist = resist
        self.immune = immune
        self.resistList = []
        self.value = 0
        
    def toString(self):
        newString = self.firstType + " " + self.secondType + " " + str(self.se) + " " + str(self.resist) + " " + str(self.immune) + " " + str(self.value)
        return newString

class TypeCalculator(object):
    def __init__(self, types, requiredTypes, pokemon):
        conn = sqlite3.connect('veekun-pokedex.sqlite')
        self.c = conn.cursor()
        self.typeCount = types
        self.requiredTypes = []
        
        self.all_pokemon = self._queryPokemon()
        self.all_types = self._queryTypes()
        self.pokemon_abilities = self._queryAbilities()
        self.pokemonUsage = dict([(self._hackPokemonNames(individualPokemon[1]), float(individualPokemon[2].strip('%'))/100) for individualPokemon in SmogonReader("smogon.txt").parse()])
        
        self.requiredPokemon = []
        for testMon in pokemon.split(','):
            if testMon != '':
                testName = self._hackPokemonNames(testMon)
                if (self._checkUsage(testName) != 0):
                    self.requiredPokemon.append(testName)
        for typeName in requiredTypes.split(','):
            if typeName != '':
                self.requiredTypes.append(self._lookupType(typeName))
        
    def generate(self):
        self.type_effectiveness = {}
        # TODO: Remove
        self.unseen = []
        
        print "Generating %d types which are super-effective against %s and includes the types %s." % (self.typeCount, self.requiredPokemon, self.requiredTypes)
        
        # Generate all Pokemon weaknesses.
        for pokemon in self.all_pokemon:
            pokemon_id = pokemon[0]
            pokemon_name = pokemon[1]
            if not self.type_effectiveness.has_key(pokemon_name):
                cur_pokemon = [instances for instances in self.all_pokemon if pokemon_id == instances[0]]
                types = {}
                for curtype in self.all_types:
                    types[curtype[1]] = 1
                    for poketype in cur_pokemon:
                        actual_type = poketype[3]
                        actual_damage = self.c.execute("SELECT damage_factor / 100.0 FROM type_efficacy WHERE damage_type_id = " + str(curtype[0]) + " AND  target_type_id = " + str(actual_type) + ";")
                        types[curtype[1]] = types[curtype[1]] * actual_damage.fetchone()[0]
                self.type_effectiveness[pokemon_name] = types
                
        print "Set up complete"        
        
        # Look up all type combinations.
        attacking_combinations = []
        possible_combinations = itertools.combinations(self.all_types, self.typeCount)

        for cur_types in possible_combinations:
            if not set(self.requiredTypes).issubset(set(list(cur_types))):
                continue
            se = []
            resist = []
            immune = []
            neutral = []
            value = 0
            #if ((11, 'Water') not in cur_types or (15, 'Ice') not in cur_types):
            #    continue
            for pokemon in self.type_effectiveness:
                damage = max([self.getDamage(cur_type[1], pokemon) for cur_type in cur_types])
                if (damage > 1):
                    se.append(pokemon)
                    value = value + 1 * self._checkUsage(pokemon)
                elif (damage == 0):
                    immune.append(pokemon)
                    value = value - 2 * self._checkUsage(pokemon)
                elif (damage < 1):
                    resist.append(pokemon)
                    value = value - 1 * self._checkUsage(pokemon)
                else:
                    neutral.append(pokemon)
            if not set(self.requiredPokemon).issubset(set(se)):
                continue
            attacking_combinations.append(Type(cur_types, se, neutral, resist, immune, value))
        
        attacking_combinations = sorted(attacking_combinations, key=lambda attack : attack.value, reverse=True)
        
        print self.all_types
        return attacking_combinations

    @memoized
    def _checkUsage(self, pokemon):
        if (self.pokemonUsage.has_key(pokemon)):
            return self.pokemonUsage[pokemon]
        self.unseen.append(pokemon);
        return 0

    def _queryPokemon(self):
        return self.c.execute("SELECT pokemon.id, pokemon.identifier, types.identifier, type_id "
                              "FROM pokemon_types, types, pokemon "
                              "WHERE type_id = types.id "
                              "AND pokemon_types.pokemon_id = pokemon.id;").fetchall()
    
    def _queryTypes(self):
        return self.c.execute("SELECT DISTINCT damage_type_id, name "
                              "FROM type_efficacy, type_names "
                              "WHERE damage_type_id = type_id "
                              "AND local_language_id = 9;").fetchall()
    
    def _queryAbilities(self):
        pokemon_abilities = {}
        for pokemon in self.all_pokemon:
            pokemon_abilities[pokemon[1]] = []
            abilities = self.c.execute('SELECT ability_id FROM pokemon_abilities WHERE pokemon_id = ' + str(pokemon[0]) + ";").fetchall();
            for ability in abilities:
                pokemon_abilities[pokemon[1]].append((self.c.execute("SELECT identifier FROM abilities WHERE id = " + str(ability[0]) + ";").fetchall()[0])[0]);
        return pokemon_abilities
    
    def _lookupType(self, typeName):
        for curType in self.all_types:
            if curType[1].lower() == typeName.lower():
                return curType
        return None
    
    def _hackPokemonNames(self, name):
        replacements = {};
        replacements["Mr. Mime".lower()] = "mr-mime"
        replacements["Mime Jr.".lower()] = "mime-jr"
        replacements["Meowstic-F".lower()] = "meowstic-female"
        replacements["Meowstic".lower()] = "meowstic-male"
        replacements["Deoxys".lower()] = "deoxys-normal"
        replacements["Farfetch'd".lower()] = "farfetchd"
        replacements["NidoranF".lower()] = "nidoran-f"
        replacements["NidoranM".lower()] = "nidoran-m"
        replacements["Landorus".lower()] = "landorus-incarnate"
        replacements["Tornadus".lower()] = "tornadus-incarnate"
        replacements["Thundurus".lower()] = "thundurus-incarnate"
        replacements["Pumpkaboo".lower()] = "pumpkaboo-average"
        replacements["Gourgeist".lower()] = "gourgeist-average"
        replacements["Aegislash".lower()] = "aegislash-shield"
        replacements["Keldeo".lower()] = "keldeo-ordinary"
        replacements["Darmanitan".lower()] = "darmanitan-standard"
        replacements["Wormadam".lower()] = "wormadam-plant"
        replacements["Basculin".lower()] = "basculin-red-striped"
        replacements["Meloetta".lower()] = "meloetta-aria"
        
        if replacements.has_key(name):
            return replacements[name]
        
        return name
    
    @memoized
    def getDamage(self, attackType, pokemon):
        abilities = self.pokemon_abilities[pokemon]
        damage = self.type_effectiveness[pokemon][attackType]
        if ("wonder-guard" in abilities and damage < 2):
            return 0
        
        # Immunities
        if (attackType == "Water" and  ("dry-skin" in abilities or "storm-drain" in abilities or "water-absorb" in abilities)):
            return 0
        if (attackType == "Fire" and ("flash-fire" in abilities)):
            return 0
        if (attackType == "Grass" and ("sap-sipper" in abilities)):
            return 0
        if (attackType == "Electric" and ("lightning-rod" in abilities or "volt-absorb" in abilities or "motor-drive" in abilities)):
            return 0
        if (attackType == "Ground" and "levitate" in abilities):
            return 0
        
        # Resistance abilities
        if (attackType == "Fire" and ("heatproof" in abilities or "thick-fat" in abilities)):
            return damage / 2
        if (attackType == "Ice" and ("thick-fat" in abilities)):
            return damage / 2
        
        return damage
    

if __name__ == "__main__":
    parser = optparse.OptionParser(
        description='Runs a program to calculate an optimal attack type selection.',
        usage='usage: %prog [option]...')
    parser.add_option('-n', '--types', default='2',
        help='The number of types to calculate (typically 2, 3 or 4)')
    parser.add_option('-r', '--required', default="",
        help='A comma separated list of required types in the attack (i.e. "water,fire,rock"'
             'It is an error to have more required types listed than types to calculate.')
    parser.add_option('-p', '--pokemon', default="",
        help='A comma separated list of Pokemon that the attack combination MUST be super-effective against.')
    
    (opts, argv) = parser.parse_args()
    
    test = TypeCalculator(int(opts.types), opts.required, opts.pokemon)
    l = test.generate()
    for x in range(min(20, len(l))):
        print l[x].toString()
        adjustedList = [item for item in l[x].resist if test._checkUsage(item) != 0 or "mega" in item]
        adjustedNeutral = [item for item in l[x].neutral if test._checkUsage(item) != 0 or "mega" in item]
        adjustedSEList = [item for item in l[x].se if test._checkUsage(item) != 0 or "mega" in item]
        print "    Top Threats SE: " + ", ".join(sorted(adjustedSEList, key=lambda name : test._checkUsage(name), reverse=True)[:10])
        print "    Top Threats Neutral: " + ", ".join(sorted(adjustedNeutral, key=lambda name : test._checkUsage(name), reverse=True)[:10])
        print "    Top Threats Resist " + ", ".join(sorted(adjustedList, key=lambda name : test._checkUsage(name), reverse=True))
        
    #unseen = [name for name in set(test.unseen) if "mega" not in name]
    #print unseen