'''
typecalculator is a calculation tool for determining optimal Pokemon attack
types through brute force analysis.

@author: Daniel Nishi
'''

from smogonreader import SmogonReader
from utils import memoized
import sqlite3
import itertools
import optparse

class Type(object):
    """
    Type is a type combination and the list of effects it has on all of the 
    Pokemon.
    """
    
    def __init__(self, new_type, super_effective, neutral, resist, immune,
                 value):
        self.types = new_type
        self.super = super_effective
        self.neutral = neutral
        self.resist = resist
        self.immune = immune
        self.value = value
        
    def to_string(self):
        """
        to_string returns a printable output of the type combination.
        """
        printable_types = [str(types[1]) for types in self.types]
        new_string = (str(printable_types) + " " + str(len(self.super)) + " " +
                      str(len(self.resist)) + " " + str(len(self.immune)) +
                      " " + str(self.value))
        return new_string

class TypeCalculator(object):
    def __init__(self, types, required_types, pokemon):
        conn = sqlite3.connect('veekun-pokedex.sqlite')
        self.conn = conn.cursor()
        self.type_count = types
        self.required_types = []
        
        self.pokemon_usage = dict([(
            self._hack_pokemon_names(individual_pokemon[1]),
            float(individual_pokemon[2].strip('%'))/100)
            for individual_pokemon in SmogonReader("smogon.txt").parse()])
        
        self.required_pokemon = []
        for testmon in pokemon.split(','):
            if testmon != '':
                test_name = self._hack_pokemon_names(testmon)
                if (self.check_usage(test_name) != 0):
                    self.required_pokemon.append(test_name)
        for type_name in required_types.split(','):
            if type_name != '':
                self.required_types.append(self._lookup_type(type_name))
        
    def generate(self):
        self.type_effectiveness = {}
        # TODO: Remove
        self.unseen = []
        
        print ("Generating %d types which are super-effective against %s and "
              "includes the types %s." % (self.type_count,
                                          self.required_pokemon,
                                          self.required_types))
        
        # Generate all Pokemon weaknesses.
        for pokemon in self._query_pokemon():
            pokemon_id = pokemon[0]
            pokemon_name = pokemon[1]
            if not self.type_effectiveness.has_key(pokemon_name):
                cur_pokemon = [instances for instances in self._query_pokemon()
                    if pokemon_id == instances[0]]
                types = {}
                for curtype in self._query_types():
                    types[curtype[1]] = 1
                    for poketype in cur_pokemon:
                        actual_type = poketype[3]
                        actual_damage = self.conn.execute(
                            ("SELECT damage_factor / 100.0 FROM type_efficacy "
                             "WHERE damage_type_id = " + str(curtype[0]) +
                             " AND  target_type_id = " + str(actual_type) + ";")
                            )
                    types[curtype[1]] = (types[curtype[1]] *
                        actual_damage.fetchone()[0])
                self.type_effectiveness[pokemon_name] = types
        
        # Look up all type combinations.
        attacking_combinations = []
        possible_combinations = itertools.combinations(self._query_types(),
                                                       self.type_count)

        for cur_types in possible_combinations:
            if not set(self.required_types).issubset(set(list(cur_types))):
                continue
            super_effective = []
            resist = []
            immune = []
            neutral = []
            value = 0
            #if ((11, 'Water') not in cur_types or (15, 'Ice') not in cur_types):
            #    continue
            for pokemon in self.type_effectiveness:
                damage = max([self.get_damage(cur_type[1], pokemon)
                              for cur_type in cur_types])
                if (damage > 1):
                    super_effective.append(pokemon)
                    value = value + 1 * self.check_usage(pokemon)
                elif (damage == 0):
                    immune.append(pokemon)
                    value = value - 2 * self.check_usage(pokemon)
                elif (damage < 1):
                    resist.append(pokemon)
                    value = value - 1 * self.check_usage(pokemon)
                else:
                    neutral.append(pokemon)
            if not set(self.required_pokemon).issubset(set(super_effective)):
                continue
            attacking_combinations.append(Type(cur_types, super_effective,
                                               neutral, resist, immune, value))
        
        attacking_combinations = sorted(attacking_combinations,
                                        key=lambda attack : attack.value,
                                        reverse=True)
        
        print self._query_types()
        return attacking_combinations

    @memoized
    def check_usage(self, pokemon):
        """
        Looks up a given Pokemon name and returns a value betwen 0 and 1 that
        is the current usage in the Smogon metagame.
        """
        if (self.pokemon_usage.has_key(pokemon)):
            return self.pokemon_usage[pokemon]
        self.unseen.append(pokemon)
        return 0

    @memoized
    def _query_pokemon(self):
        """
        Returns a list of all Pokemon in the game.
        """
        return self.conn.execute("SELECT pokemon.id, pokemon.identifier, types.identifier, type_id "
                              "FROM pokemon_types, types, pokemon "
                              "WHERE type_id = types.id "
                              "AND pokemon_types.pokemon_id = pokemon.id;").fetchall()
    
    @memoized
    def _query_types(self):
        """
        Returns a list of all Pokemon types.
        """
        return self.conn.execute("SELECT DISTINCT damage_type_id, name "
                              "FROM type_efficacy, type_names "
                              "WHERE damage_type_id = type_id "
                              "AND local_language_id = 9;").fetchall()
    
    @memoized
    def _query_abilities(self):
        """
        Returns a dict of all Pokemon to their abilities.
        """
        pokemon_abilities = {}
        for pokemon in self._query_pokemon():
            pokemon_abilities[pokemon[1]] = []
            abilities = self.conn.execute('SELECT ability_id '
                                          'FROM pokemon_abilities '
                                          'WHERE pokemon_id = ' +
                                          str(pokemon[0]) + ";").fetchall()
            for ability in abilities:
                pokemon_abilities[pokemon[1]].append((self.conn.execute(
                    "SELECT identifier "
                    "FROM abilities "
                    "WHERE id = " + str(ability[0]) + ";").fetchall()[0])[0])
        return pokemon_abilities
    
    def _lookup_type(self, type_name):
        """
        Given a type name, returns the corresponding type in db form.
        """
        for cur_type in self._query_types():
            if cur_type[1].lower() == type_name.lower():
                return cur_type
        return None
    
    def _hack_pokemon_names(self, name):
        """
        Given a Smogon usage statistics Pokemon name, return the veekun name.
        """
        replacements = {}
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
    def get_damage(self, attack_type, pokemon):
        """
        Returns the effectiveness of an attack type on a given Pokemon.
        """
        abilities = self._query_abilities()[pokemon]
        damage = self.type_effectiveness[pokemon][attack_type]
        if ("wonder-guard" in abilities and damage < 2):
            return 0
        
        # Immunities
        if (attack_type == "Water" and  ("dry-skin" in abilities
                                         or "storm-drain" in abilities
                                         or "water-absorb" in abilities)):
            return 0
        if (attack_type == "Fire" and ("flash-fire" in abilities)):
            return 0
        if (attack_type == "Grass" and ("sap-sipper" in abilities)):
            return 0
        if (attack_type == "Electric" and ("lightning-rod" in abilities
                                           or "volt-absorb" in abilities
                                           or "motor-drive" in abilities)):
            return 0
        if (attack_type == "Ground" and "levitate" in abilities):
            return 0
        
        # Resistance abilities
        if (attack_type == "Fire" and ("heatproof" in abilities
                                       or "thick-fat" in abilities)):
            return damage / 2
        if (attack_type == "Ice" and ("thick-fat" in abilities)):
            return damage / 2
        
        return damage
    

if __name__ == "__main__":
    parser = optparse.OptionParser(
        description='Runs a program to calculate optimal attack types.',
        usage='usage: %prog [option]...')
    parser.add_option('-n', '--types', default='2',
        help='The number of types to calculate (typically 2, 3 or 4)')
    parser.add_option('-r', '--required', default="",
        help='A comma separated list of required types in the attack '
             '(i.e. "water,fire,rock"'
             'It is an error to have more required types listed than types.')
    parser.add_option('-p', '--pokemon', default="",
        help='A comma separated list of Pokemon that the attack combination '
             'MUST be super-effective against.')
    
    (opts, argv) = parser.parse_args()
    
    test = TypeCalculator(int(opts.types), opts.required, opts.pokemon)
    generated = test.generate()
    for x in range(min(20, len(generated))):
        print generated[x].to_string()
        adjustedList = [item for item in generated[x].resist
                        if test.check_usage(item) != 0 or "mega" in item]
        adjustedNeutral = [item for item in generated[x].neutral
                           if test.check_usage(item) != 0 or "mega" in item]
        adjustedSEList = [item for item in generated[x].super
                          if test.check_usage(item) != 0 or "mega" in item]
        print ("    Top Threats SE: " +
            ", ".join(sorted(adjustedSEList, key=test.check_usage,
                             reverse=True)[:10]))
        print ("    Top Threats Neutral: " +
               ", ".join(sorted(adjustedNeutral, key=test.check_usage,
                                reverse=True)[:10]))
        print ("    Top Threats Resist " +
               ", ".join(sorted(adjustedList, key=test.check_usage,
                                reverse=True)))
        
    #unseen = [name for name in set(test.unseen) if "mega" not in name]
    #print unseen