import hashlib
import json
from textwrap import dedent
from urllib.parse import urlparse
from time import time
from typing import ChainMap
from uuid import uuid4

import requests
from flask import Flask, jsonify, request

class Blockchain(object):
    def __init__(self) :
        self.chain = []
        self.current_transactions = []
        self.nodes = set()

        # First block
        self.new_block(previous_hash='1', proof=100)

    def new_block(self, proof, previous_hash = None):
        # Creates a new block and adds it to the chain
        # param proof: <int> The proof given by the proof of work algo
        # param previous_hash: (optional) <str> Hash of previous block
        # return: <dict> New block

        block = {
            'index': len(self.chain) + 1,
            'timestamp': time(),
            'transactions': self.current_transactions,
            'proof': proof,
            'previous_hash': previous_hash or self.hash(self.chain[-1]),
        }

        # Reset the current list of transactions
        self.current_transactions = []
        
        self.chain.append(block)
        return block

    def new_transaction(self, sender, recipient, amount):
        # Adds a new transaction to the list of transactions
        # param sender: <str> Address of sender
        # param recipient: <str> Address of the recipient
        # param amount: <int> Amount
        # return: <int> Index of the block that will hold the transaction

        self.current_transactions.append({
            'sender': sender,
            'recipient': recipient,
            'amount': amount,
        })

        return self.last_block['index'] + 1

    def register_node(self, address):
        # add a node to list of nodes
        # :param address: <str> Address of node (ip address)
        # :return: none

        parsed_url = urlparse(address)
        self.nodes.add(parsed_url.netloc)

    def valid_chain(self, chain):
        # Determine validity of blockchain
        # :param chain: <list> A blockchain
        # :return: <bool> True if valid, False if not

        last_block = chain[0]
        current_index = 1

        while current_index < len(chain):
            block = chain[current_index]
            print(f'{last_block}')
            print(f'{block}')
            print("\n-------------------------\n")
            # Check that the hash of the block is correct
            if block['previous_hash'] != self.hash(last_block):
                return False

            # Check that POW is correct
            if not self.vaid_proof(last_block['proof'], block['proof']):
                return False
        
            last_block = block
            current_index += 1

        return True

    def resolve_conflicts(self):
        # This is the consensus algorithim
        # It replaces the chain with the longest chain in
        # the network.
        # :return: <bool> True if our chain was replaced, False otherwise

        neighbours = self.nodes
        new_chain = None

        # Looking for chains longer than ours
        max_length = len(self.chain)

        # Grab and verify the chains from all the nodes in network
        for node in neighbours:
            response = requests.get(f'http://{node}/chain')

        if response.status_code == 200:
            length = response.json()['length']
            chain = response.json()['chain']

            # Check if chain is longer and valid
            if length > max_length and self.valid_chain(chain):
                max_length = length
                new_chain = chain

        # replace chain with new, longer chain
        if new_chain:
            self.chain = new_chain
            return True

        return False

    @property
    def last_block(self):
        # Returns last block in the chain
        return self.chain[-1]

    @staticmethod
    def hash(block):
        # Creates SHA-256 hash of a block
        # param block: <dict> Block
        # return: <str>

        # Dictonary must be ordered
        block_string = json.dumps(block, sort_keys = True).encode()
        return hashlib.sha256(block_string).hexdigest()

    

    def new_transaction(self, sender, recipient, amount):
        # Creates a new transaction
        # param sender: <str> Address of sender
        # param recipient: <str> Address of recipient
        # param amount: <int> Amount
        # return: <int> index of the block holding transaction

        self.current_transactions.append({
            'sender': sender,
            'recipient': recipient,
            'amount': amount,
        })

        return self.last_block['index'] + 1

    def proof_of_work(self, last_proof):
        # Simple proof of work algo:
        # Find a number p such that hash(pp') contains leading 4 zeros, where p is previous p'
        # p is the previous proof and p' is the new proof
        # 
        # param last_proof: <int>
        # return" <int>

        proof = 0
        while self.valid_proof(last_proof, proof) is False:
            proof += 1

        return proof

    @staticmethod
    def valid_proof(last_proof, proof):
        # Validate proof: does hash(last_proof, proof) contain 4 leading zeros
        # param last_proof: <int> Previous proof
        # param proof: <int> current proof
        # return: <bool> True if correct, false otherwise

        guess = f'{last_proof}{proof}'.encode()
        guess_hash = hashlib.sha256(guess).hexdigest()
        return guess_hash[:4] == "0000"


# Instantiate Node

app = Flask(__name__)

# Generate unique address for node
node_identifier = str(uuid4()).replace('-', '')

# Instantiate blockchain
blockchain = Blockchain()

@app.route('/mine', methods = ['GET'])
def mine():
    # Run the POW algorithm to get next proof
    last_block = blockchain.last_block
    last_proof = last_block['proof']
    proof = blockchain.proof_of_work(last_proof)

    # We have to give a reward for finding the proof
    # The sender is '0' to signify that this node mined a new coin
    blockchain.new_transaction(
        sender = "0",
        recipient = node_identifier,
        amount = 1,
    )

    # Create new block by adding it to chain
    previous_hash = blockchain.hash(last_block)
    block = blockchain.new_block(proof, previous_hash)

    response = {
        'message': "New block created",
        'index': block['index'],
        'transactions': block['transactions'],
        'proof': block['proof'],
        'previous_hash': block['previous_hash'],
    }
    return jsonify(response), 200

@app.route('/transactions/new', methods=['POST'])
def new_transaction():
    values = request.get_json(force = True)

    # Check that the required fields are in the POST'ed data
    required = ['sender', 'recipient', 'amount']
    if not all(k in values for k in required):
        return 'Missing values', 400

    # Create a new Transaction
    index = blockchain.new_transaction(values['sender'], values['recipient'], values['amount'])

    response = {'message': f'Transaction will be added to Block {index}'}
    return jsonify(response), 201

@app.route('/chain', methods = ['GET'])
def full_chain():
    response = {
        'chain': blockchain.chain,
        'length': len(blockchain.chain),
    }
    return jsonify(response), 200

@app.route('/nodes/register', methods=['POST'])
def register_nodes():
    values = request.get_json()

    nodes = values.get('nodes')
    if nodes is None:
        return 'Error: Please supply valid nodes', 400

    for node in nodes:
        blockchain.register_node(node)

    response = {
        "message": "New nodes have been added",
        "total_nodes": list(blockchain.nodes)
    }
    return jsonify(response), 201

@app.route('/nodes/resolve', methods=['GET'])
def consensus():
    replaced = blockchain.resolve_conflicts()

    if replaced:
        response = {
            'message': 'Our chain was replaced',
            'new_chain': blockchain.chain
        }
    else:
        response = {
            'message': 'Our chain is authoritative',
            'chain': blockchain.chain
        }

    return jsonify(response), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port = 5000)





