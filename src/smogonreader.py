'''
SmogonReader is a reader of Smogon usage files.

@author: daniel
'''

class SmogonReader(object):
    def __init__(self, filePath):
        with open(filePath) as f:
            self.content = f.readlines()
    
    def parse(self):
        parameters = []
        for line in self.content:
            if not _contains_digits(line):
                continue
            parameters.append([x.lower().strip() for x in line.split('|') if x.strip() != ''])
        return parameters

def _contains_digits(s):
        return any(char.isdigit() for char in s)

class ChecksAndCountersReader(object):
    def __init__(self, filePath):
        with open(filePath) as f:
            self.content = f.readlines()
            
    def parse(self):
        parseNext = False
        for line in self.content:
            if parseNext:
                print line.split(" ")
                parseNext = False
            if self._skipJunk(line):
                parseNext = True
                continue
            
            
            
    def _skipJunk(self, line):
        return "Checks and Counters" in line;

if __name__ == "__main__":
    #test = SmogonReader("smogon.txt")
    test = ChecksAndCountersReader("checks.txt")
    test.parse()